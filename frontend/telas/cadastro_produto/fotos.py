from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt, QBuffer, QIODevice
from PySide6.QtGui import QPixmap

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
)

import base64

from services.produto_service import (
    obter_foto_produto,
)
from services.produto_foto_service import (
    listar_fotos_produto,
    obter_imagem_foto,
    adicionar_foto_produto,
    remover_foto_produto,
    marcar_foto_principal,
)
from services.worker import rodar_em_thread
from design import tokens
from design.icons import icone
from telas.cadastro_produto.comum import _FOTO_ALTURA, _FOTO_LARGURA


def _buscar_miniatura_com_info(produto_id, foto):
    """Roda na worker thread -- 'foto' (os metadados, id/ordem/
    principal) viaja junto com os bytes da imagem baixada, mesmo
    motivo de _criar_categoria_com_nome."""
    return foto, obter_imagem_foto(produto_id, foto["id"])


class FotosMixin:
    """Foto principal e galeria de fotos extras."""

    def adicionar_imagem(self):

        caminho, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Imagem",
            "",
            "Imagens (*.png *.jpg *.jpeg *.bmp *.webp)",
        )

        if not caminho:
            return

        imagem_comprimida = self._comprimir_imagem(caminho)

        if imagem_comprimida is None:
            QMessageBox.warning(
                self,
                "Imagem inválida",
                "Não foi possível abrir essa imagem."
            )
            return

        self.imagem_bytes = imagem_comprimida

        self._exibir_imagem(self.imagem_bytes)

    def _comprimir_imagem(self, caminho, lado_maximo=640, qualidade=82):
        """Reduz a foto pro tamanho real de exibição (miniatura na
        lista de produtos, no PDV etc.) antes de mandar pro backend --
        sem isso, uma foto tirada direto do celular (facilmente
        3-5 MB) ia inteira pro banco, e a lista de produtos (que
        carrega uma foto por linha) ficava visivelmente lenta pra
        abrir. JPEG a essa qualidade fica imperceptível numa
        miniatura de ~50px e ocupa uma fração do tamanho original."""

        pixmap = QPixmap(caminho)

        if pixmap.isNull():
            return None

        if pixmap.width() > lado_maximo or pixmap.height() > lado_maximo:
            pixmap = pixmap.scaled(
                lado_maximo, lado_maximo,
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )

        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        pixmap.save(buffer, "JPEG", qualidade)

        return bytes(buffer.data())

    def _exibir_imagem(self, imagem_bytes):

        pixmap = QPixmap()
        pixmap.loadFromData(imagem_bytes)

        if pixmap.isNull():
            QMessageBox.warning(
                self,
                "Imagem inválida",
                "Não foi possível abrir essa imagem."
            )
            return

        self.lbl_foto.setPixmap(
            pixmap.scaled(
                _FOTO_LARGURA, _FOTO_ALTURA,
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
        )

    # ==========================================
    # GALERIA DE FOTOS (edição apenas)
    # ==========================================

    def _carregar_galeria_fotos(self):
        rodar_em_thread(
            self,
            listar_fotos_produto,
            self.produto["id"],
            ao_sucesso=self._ao_carregar_galeria_sucesso,
        )

    def _ao_carregar_galeria_sucesso(self, fotos):

        # remove todas as miniaturas antigas, mantendo so' o botao "+"
        # (sempre o primeiro item do layout)
        while self.linha_galeria.count() > 2:
            item = self.linha_galeria.takeAt(1)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for foto in fotos:
            rodar_em_thread(
                self,
                _buscar_miniatura_com_info,
                self.produto["id"],
                foto,
                ao_sucesso=self._ao_carregar_miniatura_sucesso,
            )

    def _ao_carregar_miniatura_sucesso(self, resultado):

        foto, imagem_bytes = resultado

        if not imagem_bytes:
            return

        miniatura = self._construir_miniatura_foto(foto, imagem_bytes)
        # insere antes do addStretch() (ultimo item do layout)
        self.linha_galeria.insertWidget(
            self.linha_galeria.count() - 1, miniatura
        )

    def _construir_miniatura_foto(self, foto, imagem_bytes):

        quadro = QFrame()
        quadro.setFixedSize(56, 76)
        quadro.setStyleSheet("background:transparent; border:none;")

        col = QVBoxLayout(quadro)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)

        lbl_img = QLabel()
        lbl_img.setFixedSize(56, 56)
        lbl_img.setAlignment(Qt.AlignCenter)
        borda = tokens.PRIMARIA if foto.get("principal") else tokens.BORDA
        lbl_img.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px;
            border:2px solid {borda};
        """)

        pixmap = QPixmap()
        pixmap.loadFromData(imagem_bytes)
        if not pixmap.isNull():
            lbl_img.setPixmap(
                pixmap.scaled(
                    52, 52, Qt.KeepAspectRatio, Qt.SmoothTransformation,
                )
            )

        linha_acoes = QHBoxLayout()
        linha_acoes.setSpacing(2)
        linha_acoes.setContentsMargins(0, 0, 0, 0)

        bt_principal = QPushButton()
        bt_principal.setFixedSize(20, 18)
        bt_principal.setCursor(Qt.PointingHandCursor)
        bt_principal.setToolTip(
            "Foto principal" if foto.get("principal")
            else "Tornar principal"
        )
        bt_principal.setAccessibleName(bt_principal.toolTip())
        bt_principal.setIcon(
            icone(
                "star-filled" if foto.get("principal") else "star",
                cor=tokens.ALERTA if foto.get("principal") else tokens.TEXTO_TERCIARIO,
                tamanho=12,
            )
        )
        bt_principal.setEnabled(not foto.get("principal"))
        bt_principal.setStyleSheet(
            "background:transparent; border:none;"
        )
        bt_principal.clicked.connect(
            lambda: self._tornar_foto_principal(foto["id"])
        )

        bt_excluir = QPushButton()
        bt_excluir.setFixedSize(20, 18)
        bt_excluir.setCursor(Qt.PointingHandCursor)
        bt_excluir.setToolTip("Remover foto")
        bt_excluir.setAccessibleName("Remover foto")
        bt_excluir.setIcon(icone("trash-2", cor=tokens.ERRO, tamanho=12))
        bt_excluir.setStyleSheet("background:transparent; border:none;")
        bt_excluir.clicked.connect(
            lambda: self._remover_foto_extra(foto["id"])
        )

        linha_acoes.addWidget(bt_principal)
        linha_acoes.addWidget(bt_excluir)

        col.addWidget(lbl_img)
        col.addLayout(linha_acoes)

        return quadro

    def adicionar_foto_extra(self):

        caminho, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Imagem",
            "",
            "Imagens (*.png *.jpg *.jpeg *.bmp *.webp)",
        )

        if not caminho:
            return

        imagem_comprimida = self._comprimir_imagem(caminho)

        if imagem_comprimida is None:
            QMessageBox.warning(
                self, "Imagem inválida", "Não foi possível abrir essa imagem."
            )
            return

        imagem_base64 = base64.b64encode(imagem_comprimida).decode("ascii")

        self.bt_adicionar_foto_extra.setEnabled(False)

        rodar_em_thread(
            self,
            adicionar_foto_produto,
            self.produto["id"],
            imagem_base64,
            False,
            ao_sucesso=self._ao_mutar_galeria_sucesso,
            ao_erro=self._ao_mutar_galeria_erro,
            ao_finalizar=self._ao_mutar_galeria_finalizado,
        )

    def _tornar_foto_principal(self, foto_id):
        rodar_em_thread(
            self,
            marcar_foto_principal,
            self.produto["id"],
            foto_id,
            ao_sucesso=self._ao_mutar_galeria_sucesso,
            ao_erro=self._ao_mutar_galeria_erro,
        )

    def _remover_foto_extra(self, foto_id):

        resposta = QMessageBox.question(
            self, "Remover foto", "Remover essa foto do produto?"
        )

        if resposta != QMessageBox.Yes:
            return

        rodar_em_thread(
            self,
            remover_foto_produto,
            self.produto["id"],
            foto_id,
            ao_sucesso=self._ao_mutar_galeria_sucesso,
            ao_erro=self._ao_mutar_galeria_erro,
        )

    def _ao_mutar_galeria_sucesso(self, response):

        if response.status_code in (200, 201):
            self._carregar_galeria_fotos()
            # a principal pode ter mudado (marcar/remover) -- recarrega
            # tambem a previa grande de cima, que le da mesma fonte
            rodar_em_thread(
                self,
                obter_foto_produto,
                self.produto["id"],
                ao_sucesso=self._ao_carregar_foto_sucesso,
            )
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

    def _ao_mutar_galeria_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_mutar_galeria_finalizado(self):
        self.bt_adicionar_foto_extra.setEnabled(True)
