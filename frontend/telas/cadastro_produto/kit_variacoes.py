from PySide6.QtWidgets import QMessageBox

from PySide6.QtWidgets import (
    QDialog,
    QInputDialog,
    QTableWidgetItem,
)


from services.produto_service import (
    listar_produtos,
    cadastrar_produto,
    listar_variacoes,
)
from services.kit_item_service import (
    listar_itens_kit,
    adicionar_item_kit,
    remover_item_kit,
)
from services.worker import rodar_em_thread
from widgets.dialogs.pesquisa_window import PesquisaWindow


class KitVariacoesMixin:
    """Produto kit (componentes) e variacoes (produto pai/filho)."""

    # ==========================================
    # KIT / COMBO
    # ==========================================

    def _alternar_kit(self, marcado):
        habilitado = marcado and self.produto is not None
        self.bt_adicionar_componente.setEnabled(habilitado)
        self.bt_remover_componente.setEnabled(habilitado)

    def _carregar_itens_kit(self):
        rodar_em_thread(
            self,
            listar_itens_kit,
            self.produto["id"],
            ao_sucesso=self._ao_carregar_itens_kit_sucesso,
            ao_erro=self._ao_carregar_itens_kit_erro,
        )

    def _ao_carregar_itens_kit_sucesso(self, itens):
        self.kit_itens = itens

        self.tabela_kit.setRowCount(len(itens))

        for linha, item in enumerate(itens):
            self.tabela_kit.setItem(
                linha, 0,
                QTableWidgetItem(item.get("produto_componente_nome") or ""),
            )
            self.tabela_kit.setItem(
                linha, 1, QTableWidgetItem(str(item["quantidade"]))
            )

    def _ao_carregar_itens_kit_erro(self, erro):
        QMessageBox.critical(
            self, "Erro",
            f"Não foi possível carregar os componentes do kit.\n{erro}"
        )

    def adicionar_componente_kit(self):

        if not self.produto:
            return

        rodar_em_thread(
            self,
            listar_produtos,
            ao_sucesso=self._ao_listar_produtos_para_kit,
            ao_erro=self._ao_carregar_itens_kit_erro,
        )

    def _ao_listar_produtos_para_kit(self, produtos):

        candidatos = [
            p for p in produtos
            if p["id"] != self.produto["id"] and not p.get("eh_kit")
        ]

        tela = PesquisaWindow(
            titulo="Adicionar componente do kit",
            colunas=["Código", "Nome", "Estoque"],
            campos=["codigo", "nome", "estoque"],
            dados=candidatos,
            chave_pesquisa="nome",
        )

        if tela.exec() != QDialog.Accepted:
            return

        quantidade, ok = QInputDialog.getInt(
            self, "Quantidade",
            f"Quantos \"{tela.selecionado['nome']}\" entram em 1 unidade "
            "do kit?",
            1, 1, 999999,
        )

        if not ok:
            return

        rodar_em_thread(
            self,
            adicionar_item_kit,
            self.produto["id"],
            tela.selecionado["id"],
            quantidade,
            ao_sucesso=self._ao_mutar_kit_sucesso,
            ao_erro=self._ao_carregar_itens_kit_erro,
        )

    def remover_componente_kit(self):

        linha = self.tabela_kit.currentRow()

        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione um componente.")
            return

        item = self.kit_itens[linha]

        rodar_em_thread(
            self,
            remover_item_kit,
            self.produto["id"],
            item["id"],
            ao_sucesso=self._ao_mutar_kit_sucesso,
            ao_erro=self._ao_carregar_itens_kit_erro,
        )

    def _ao_mutar_kit_sucesso(self, response):
        if response.status_code in (200, 201):
            self._carregar_itens_kit()
        else:
            try:
                erro = response.json().get("detail") or str(response.json())
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

    # ==========================================
    # VARIACOES (COR/TAMANHO)
    # ==========================================

    def _carregar_variacoes(self):
        rodar_em_thread(
            self,
            listar_variacoes,
            self.produto["id"],
            ao_sucesso=self._ao_carregar_variacoes_sucesso,
            ao_erro=self._ao_carregar_variacoes_erro,
        )

    def _ao_carregar_variacoes_sucesso(self, variacoes):
        self.tabela_variacoes.setRowCount(len(variacoes))

        for linha, v in enumerate(variacoes):
            self.tabela_variacoes.setItem(
                linha, 0, QTableWidgetItem(v.get("nome") or "")
            )
            self.tabela_variacoes.setItem(
                linha, 1, QTableWidgetItem(v.get("cor") or "")
            )
            self.tabela_variacoes.setItem(
                linha, 2, QTableWidgetItem(v.get("tamanho") or "")
            )
            self.tabela_variacoes.setItem(
                linha, 3, QTableWidgetItem(str(v.get("estoque", 0)))
            )

    def _ao_carregar_variacoes_erro(self, erro):
        QMessageBox.critical(
            self, "Erro",
            f"Não foi possível carregar as variações.\n{erro}"
        )

    def nova_variacao(self):

        if not self.produto:
            return

        # import local: cadastro_produto.py importa este mixin (ciclo)
        from telas.cadastro_produto.cadastro_produto import CadastroProdutoWindow

        tela = CadastroProdutoWindow(produto_pai=self.produto)

        if tela.exec() != QDialog.Accepted:
            return

        self._nova_variacao_tela = tela

        rodar_em_thread(
            self,
            cadastrar_produto,
            tela.dados,
            ao_sucesso=self._ao_nova_variacao_sucesso,
            ao_erro=self._ao_carregar_variacoes_erro,
        )

    def _ao_nova_variacao_sucesso(self, response):
        if response.status_code == 201:
            self._carregar_variacoes()
        else:
            try:
                erro = response.json().get("detail") or str(response.json())
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))
