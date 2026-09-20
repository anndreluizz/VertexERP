from datetime import datetime

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidgetItem,
    QMessageBox,
)

from services.auditoria_service import listar_logs_auditoria
from services.worker import rodar_em_thread
from widgets.tables.standard_table import StandardTable
from design import tokens
from design.widgets import BotaoSecundario, CampoTexto


class LogAuditoriaDialog(QDialog):
    """So' leitura -- quem exerceu uma acao sensivel (qualquer coisa
    gatada por exigir_permissao/get_current_admin no backend), quando
    e de que IP. Nao mostra diff de campo por campo (ver
    app/models/log_auditoria.py no backend pro porque)."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Log de Auditoria")
        self.resize(720, 560)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        titulo = QLabel("Log de Auditoria")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        layout.addWidget(titulo)

        filtro_layout = QHBoxLayout()

        self.filtro_acao = CampoTexto(
            "Filtrar por ação (ex.: produtos.excluir)...",
            cor_foco=tokens.PRIMARIA,
        )
        self.filtro_acao.returnPressed.connect(self.carregar)
        filtro_layout.addWidget(self.filtro_acao, stretch=1)

        bt_filtrar = BotaoSecundario("Filtrar")
        bt_filtrar.clicked.connect(self.carregar)
        filtro_layout.addWidget(bt_filtrar)

        bt_limpar = BotaoSecundario("Limpar")
        bt_limpar.clicked.connect(self.limpar_filtro)
        filtro_layout.addWidget(bt_limpar)

        layout.addLayout(filtro_layout)

        self.tabela = StandardTable(
            ["Data", "Usuário", "Ação", "IP", "Detalhes"]
        )
        layout.addWidget(self.tabela, stretch=1)

        rodape = QHBoxLayout()
        rodape.addStretch()

        bt_fechar = BotaoSecundario("Fechar")
        bt_fechar.clicked.connect(self.accept)
        rodape.addWidget(bt_fechar)

        layout.addLayout(rodape)

        self.carregar()

    def limpar_filtro(self):
        self.filtro_acao.clear()
        self.carregar()

    def carregar(self):
        rodar_em_thread(
            self,
            listar_logs_auditoria,
            None,
            self.filtro_acao.text().strip() or None,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
        )

    def _ao_carregar_sucesso(self, logs):

        self.tabela.setRowCount(len(logs))

        for linha, log in enumerate(logs):
            data = datetime.fromisoformat(log["data"]).strftime(
                "%d/%m/%Y %H:%M"
            )
            self.tabela.setItem(linha, 0, QTableWidgetItem(data))
            self.tabela.setItem(
                linha, 1, QTableWidgetItem(log.get("usuario_nome") or "—")
            )
            self.tabela.setItem(linha, 2, QTableWidgetItem(log["acao"]))
            self.tabela.setItem(
                linha, 3, QTableWidgetItem(log.get("ip") or "")
            )
            self.tabela.setItem(
                linha, 4, QTableWidgetItem(log.get("detalhes") or "")
            )

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível carregar a auditoria.\n{erro}"
        )
