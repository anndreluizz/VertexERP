from PySide6.QtWidgets import QInputDialog, QMessageBox


from services import api
from services.ean_lookup import buscar_produto_externo
from services.estoque_service import ajustar_estoque
from services.pdv_service import buscar_produto
from services.worker import rodar_em_thread
from design import tokens


def _buscar_produto_externo_com_flag(codigo, silencioso, conferir_local):
    """Roda na worker thread -- 'silencioso' viaja junto com o
    resultado pelo mesmo motivo de _criar_categoria_com_nome.
    Antes da base publica confere se o codigo ja' esta' cadastrado
    aqui: devolve (produto_local, externo, silencioso)."""
    if conferir_local:
        local = buscar_produto(codigo)
        if local:
            return local, None, silencioso
    return None, buscar_produto_externo(codigo), silencioso


class BuscaExternaMixin:
    """Modo de cadastro e busca automatica do produto pelo codigo de barras."""

    # ==========================================
    # MODO DE VENDA (UNID / PESO / LITRO)
    # ==========================================

    def selecionar_modo(self, valor):

        self.modo_venda = valor

        for chave, botao in self.botoes_modo.items():

            selecionado = chave == valor
            botao.setChecked(selecionado)

            botao.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens.PRIMARIA_CLARA if selecionado else tokens.CARD};
                    color: {tokens.PRIMARIA if selecionado else tokens.TEXTO_SECUNDARIO};
                    border: 1.5px solid {tokens.PRIMARIA if selecionado else tokens.BORDA};
                    border-radius: {tokens.RADIUS_SM}px;
                    font-weight: {700 if selecionado else 600};
                    font-size: {tokens.TAMANHO_SM}px;
                }}
                QPushButton:hover {{
                    border-color: {tokens.PRIMARIA};
                }}
            """)

        # o resumo mostra a unidade junto do estoque
        if hasattr(self, "lbl_resumo_estoque"):
            self._atualizar_margem()

    # ==========================================
    # BUSCA AUTOMÁTICA PELO CÓDIGO DE BARRAS
    # ==========================================

    def agendar_busca_automatica(self, texto):

        self.timer_busca_automatica.stop()

        # so dispara sozinho com tamanho de codigo de barras de
        # verdade, pra nao ficar buscando a cada digito
        if len(texto.strip()) >= 8:
            self.timer_busca_automatica.start(400)

    def buscar_automatico(self, silencioso=False):

        # Enter e o timer chegam juntos pro mesmo codigo -- uma busca so'
        self.timer_busca_automatica.stop()

        codigo = self.codigo_barras.text().strip()

        if not codigo:
            if not silencioso:
                QMessageBox.information(
                    self,
                    "Buscar produto",
                    "Informe um código de barras para buscar."
                )
            return

        self.bt_buscar.setEnabled(False)

        rodar_em_thread(
            self,
            _buscar_produto_externo_com_flag,
            codigo,
            silencioso,
            # editando, o codigo "ja cadastrado" e' o do proprio produto
            self.produto is None,
            ao_sucesso=self._ao_buscar_automatico_sucesso,
            ao_erro=self._ao_buscar_automatico_erro,
            ao_finalizar=self._ao_buscar_automatico_finalizado,
        )

    def _ao_buscar_automatico_sucesso(self, resultado_com_flag):

        local, resultado, silencioso = resultado_com_flag

        if local:
            self._produto_ja_cadastrado(local)
            return

        if resultado is None:

            if not silencioso:
                QMessageBox.information(
                    self,
                    "Buscar produto",
                    "Produto não encontrado na base pública "
                    "(Open Food Facts). Cadastre os dados manualmente."
                )
            return

        self.nome.setText(resultado["nome"])

        if resultado["imagem_bytes"]:

            self.imagem_bytes = resultado["imagem_bytes"]
            self._exibir_imagem(self.imagem_bytes)

    def _produto_ja_cadastrado(self, produto):
        """Bipou um codigo que ja' existe: em vez de cadastrar de novo,
        oferece somar ao estoque e volta pro campo pro proximo bipe."""

        texto = (
            f"\"{produto['nome']}\" já está cadastrado "
            f"(código {produto['codigo']}, estoque atual {produto['estoque']})."
        )

        if not api.usuario_tem_permissao("estoque.ajustar"):
            QMessageBox.information(self, "Produto já cadastrado", texto)
        else:
            quantidade, ok = QInputDialog.getInt(
                self, "Produto já cadastrado",
                texto + "\n\nQuantas unidades adicionar ao estoque?",
                1, 1, 100000,
            )
            if ok:
                resposta = ajustar_estoque({
                    "produto_id": produto["id"],
                    "tipo": "ENTRADA",
                    "quantidade": quantidade,
                    "motivo": "Entrada pelo cadastro de produto",
                })
                if resposta.status_code == 201:
                    QMessageBox.information(
                        self, "Estoque atualizado",
                        f"+{quantidade} em \"{produto['nome']}\" "
                        f"(agora {produto['estoque'] + quantidade}).",
                    )
                else:
                    QMessageBox.critical(
                        self, "Erro",
                        f"Não foi possível adicionar ao estoque.\n{resposta.text}",
                    )

        self.codigo_barras.clear()
        self.codigo_barras.setFocus()

    def _ao_buscar_automatico_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível buscar o produto.\n{erro}"
        )

    def _ao_buscar_automatico_finalizado(self):
        self.bt_buscar.setEnabled(True)
