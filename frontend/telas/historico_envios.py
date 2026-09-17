from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
)

from design import tokens
from services import comprovante_service
from services.worker import rodar_em_thread


class HistoricoEnviosDialog(QDialog):
    """Data/hora, usuário, canal, destino e status de cada tentativa
    de envio do comprovante de uma venda -- nunca apagado (ver
    ComprovanteEnvio no backend), pra quem for conferir depois se o
    cliente recebeu ou não."""

    def __init__(self, venda_id, parent=None):

        super().__init__(parent)

        self.venda_id = venda_id

        self.setWindowTitle("Histórico de Envios")
        self.setMinimumSize(560, 420)
        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        titulo = QLabel(f"Histórico de Envios — Venda #{venda_id}")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:700; color:{tokens.TEXTO};
        """)
        layout.addWidget(titulo)

        self.tabela = QTableWidget()
        self.tabela.setColumnCount(5)
        self.tabela.setHorizontalHeaderLabels(
            ["Data/Hora", "Usuário", "Canal", "Destino", "Status"]
        )
        self.tabela.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setSelectionMode(QTableWidget.NoSelection)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setStyleSheet(f"""
            QTableWidget {{
                background:{tokens.CARD}; alternate-background-color:{tokens.FUNDO};
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_MD}px;
                color:{tokens.TEXTO}; font-size:{tokens.TAMANHO_SM}px;
            }}
            QHeaderView::section {{
                background:{tokens.FUNDO}; color:{tokens.TEXTO_SECUNDARIO};
                padding:8px; border:none; border-bottom:1px solid {tokens.BORDA};
                font-weight:700; font-size:{tokens.TAMANHO_XS}px;
            }}
        """)
        layout.addWidget(self.tabela, stretch=1)

        bt_fechar = QPushButton("Fechar")
        bt_fechar.setMinimumHeight(40)
        bt_fechar.clicked.connect(self.accept)
        layout.addWidget(bt_fechar)

        self.carregar()

    def carregar(self):

        self.tabela.setRowCount(1)
        item = QTableWidgetItem("Carregando...")
        item.setForeground(QColor(tokens.TEXTO_TERCIARIO))
        self.tabela.setItem(0, 0, item)
        self.tabela.setSpan(0, 0, 1, 5)

        rodar_em_thread(
            self,
            comprovante_service.buscar_historico_envios,
            self.venda_id,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
        )

    def _ao_carregar_erro(self, erro):
        self.tabela.setRowCount(1)
        item = QTableWidgetItem(f"Não foi possível carregar o histórico. {erro}")
        item.setForeground(QColor(tokens.ERRO))
        self.tabela.setItem(0, 0, item)
        self.tabela.setSpan(0, 0, 1, 5)

    def _ao_carregar_sucesso(self, envios):

        self.tabela.setRowCount(len(envios))

        for linha, envio in enumerate(envios):

            data = str(envio.get("data") or "").replace("T", " ")[:16]
            usuario = envio.get("usuario_nome") or "—"
            canal = "WhatsApp" if envio["canal"] == "WHATSAPP" else "E-mail"
            destino = envio.get("destino") or "—"
            status = envio.get("status") or "—"

            cor = tokens.SECUNDARIA if status == "ENVIADO" else tokens.ERRO
            texto_status = "Enviado" if status == "ENVIADO" else "Falhou"

            for coluna, valor in enumerate(
                [data, usuario, canal, destino, texto_status]
            ):
                item = QTableWidgetItem(valor)
                if coluna == 4:
                    item.setForeground(QColor(cor))
                self.tabela.setItem(linha, coluna, item)

        if not envios:
            self.tabela.setRowCount(1)
            item = QTableWidgetItem("Nenhum envio registrado ainda.")
            item.setForeground(QColor(tokens.TEXTO_TERCIARIO))
            self.tabela.setItem(0, 0, item)
            self.tabela.setSpan(0, 0, 1, 5)
