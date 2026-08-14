from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from design import tokens
from design.responsive import tamanho_fixo_seguro
from utils.formatacao import formatar_moeda


class ProdutoCriadoDialog(QDialog):

    def __init__(self, nome, preco_venda, imagem_bytes=None, parent=None):

        super().__init__(parent)

        self.editar_solicitado = False

        self.setWindowTitle("Produto Criado")
        tamanho_fixo_seguro(self, 420, 500)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 30, 36, 30)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignHCenter)

        titulo = QLabel("Produto Criado!")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet(
            "background:transparent; font-size:22px; "
            f"font-weight:bold; color:{tokens.TEXTO};"
        )

        subtitulo = QLabel("O item já está disponível no estoque")
        subtitulo.setAlignment(Qt.AlignCenter)
        subtitulo.setStyleSheet(
            f"background:transparent; font-size:11px; color:{tokens.TEXTO_SECUNDARIO};"
        )

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(14)

        selo = QLabel("✨")
        selo.setFixedSize(48, 48)
        selo.setAlignment(Qt.AlignCenter)
        selo.setStyleSheet(f"""
            background:{tokens.SECUNDARIA};
            color:{tokens.TEXTO_CLARO};
            font-size:20px;
            border-radius:24px;
        """)
        layout.addWidget(selo, alignment=Qt.AlignHCenter)

        self.lbl_imagem = QLabel("📦")
        self.lbl_imagem.setFixedSize(140, 140)
        self.lbl_imagem.setAlignment(Qt.AlignCenter)
        self.lbl_imagem.setStyleSheet(f"""
            background:{tokens.FUNDO};
            border-radius:16px;
            font-size:48px;
        """)

        if imagem_bytes:
            pixmap = QPixmap()
            pixmap.loadFromData(imagem_bytes)
            self.lbl_imagem.setText("")
            self.lbl_imagem.setPixmap(
                pixmap.scaled(
                    140,
                    140,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )

        layout.addWidget(self.lbl_imagem, alignment=Qt.AlignHCenter)

        lbl_nome = QLabel(nome.upper())
        lbl_nome.setAlignment(Qt.AlignCenter)
        lbl_nome.setWordWrap(True)
        lbl_nome.setStyleSheet(
            "background:transparent; font-size:16px; "
            f"font-weight:bold; color:{tokens.TEXTO};"
        )

        lbl_preco = QLabel(formatar_moeda(preco_venda))
        lbl_preco.setAlignment(Qt.AlignCenter)
        lbl_preco.setStyleSheet(f"""
            background:{tokens.SUCESSO_CLARO};
            color:{tokens.SECUNDARIA_HOVER};
            font-size:14px;
            font-weight:bold;
            border-radius:12px;
            padding:4px 14px;
        """)

        layout.addWidget(lbl_nome)
        layout.addWidget(lbl_preco, alignment=Qt.AlignHCenter)
        layout.addSpacing(16)

        bt_concluir = QPushButton("Concluir")
        bt_concluir.setMinimumHeight(46)
        bt_concluir.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.SECUNDARIA};
                color:{tokens.TEXTO_CLARO};
                font-weight:bold;
                border-radius:10px;
            }}
            QPushButton:hover {{
                background:{tokens.SECUNDARIA_HOVER};
            }}
        """)
        bt_concluir.clicked.connect(self.accept)

        bt_editar = QPushButton("Editar Detalhes")
        bt_editar.setMinimumHeight(46)
        bt_editar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD};
                color:{tokens.TEXTO};
                border:1px solid {tokens.BORDA};
                border-radius:10px;
            }}
            QPushButton:hover {{
                background:{tokens.FUNDO};
            }}
        """)
        bt_editar.clicked.connect(self.editar)

        layout.addWidget(bt_concluir)
        layout.addWidget(bt_editar)

    def editar(self):
        self.editar_solicitado = True
        self.accept()
