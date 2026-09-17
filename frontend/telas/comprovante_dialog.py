from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTextBrowser,
    QMessageBox,
)

from design import tokens
from design.animations import fade_in
from design.widgets import BotaoPrimario, BotaoSecundario
from services import comprovante_service
from services.api import configuracoes
from services.worker import rodar_em_thread
from telas import comprovante_acoes
from telas.historico_envios import HistoricoEnviosDialog


def _buscar_dados_comprovante(venda_id):
    """Roda na worker thread -- as 3 chamadas que
    ComprovanteDialog.carregar() precisa."""
    dados = comprovante_service.buscar_dados_comprovante(venda_id)

    if not dados:
        return None

    config = configuracoes()
    logo = comprovante_service.obter_logo_loja()

    return comprovante_service.gerar_html_comprovante(dados, config, logo)


class ComprovanteDialog(QDialog):
    """Visualizador de comprovante reutilizável -- tanto pra 'Visualizar
    Comprovante' logo após finalizar a venda quanto pra reabrir o
    comprovante de qualquer venda antiga (ficha do cliente, etc). O
    comprovante em si nunca é apagado: é sempre remontado na hora a
    partir da Venda salva no banco, então não existe 'arquivo perdido'
    -- ver VendaService.montar_comprovante no backend."""

    def __init__(self, venda_id, parent=None):

        super().__init__(parent)

        self.venda_id = venda_id

        self.setWindowTitle("Comprovante (não fiscal)")
        self.setMinimumSize(460, 640)
        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.area = QTextBrowser()
        self.area.setOpenExternalLinks(False)
        self.area.setStyleSheet(f"""
            QTextBrowser {{
                background:white; border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_MD}px; padding:10px;
            }}
        """)
        layout.addWidget(self.area, stretch=1)

        linha1 = QHBoxLayout()
        linha1.setSpacing(8)

        self.bt_imprimir = BotaoSecundario("Imprimir", icone_nome="printer")
        self.bt_imprimir.setMinimumHeight(42)
        self.bt_imprimir.clicked.connect(self.imprimir)

        self.bt_baixar = BotaoSecundario("Baixar PDF", icone_nome="download")
        self.bt_baixar.setMinimumHeight(42)
        self.bt_baixar.clicked.connect(self.baixar)

        linha1.addWidget(self.bt_imprimir)
        linha1.addWidget(self.bt_baixar)
        layout.addLayout(linha1)

        linha2 = QHBoxLayout()
        linha2.setSpacing(8)

        self.bt_whatsapp = BotaoPrimario(
            "Enviar pelo WhatsApp", icone_nome="message-circle"
        )
        self.bt_whatsapp.setMinimumHeight(42)
        self.bt_whatsapp.clicked.connect(self.enviar_whatsapp)

        self.bt_email = BotaoPrimario("Enviar por E-mail", icone_nome="mail")
        self.bt_email.setMinimumHeight(42)
        self.bt_email.clicked.connect(self.enviar_email)

        linha2.addWidget(self.bt_whatsapp)
        linha2.addWidget(self.bt_email)
        layout.addLayout(linha2)

        self.bt_historico = BotaoSecundario(
            "Histórico de Envios", icone_nome="file-text"
        )
        self.bt_historico.setMinimumHeight(38)
        self.bt_historico.clicked.connect(self.abrir_historico)
        layout.addWidget(self.bt_historico)

        self.carregar()

        fade_in(self, duracao=200)

    def carregar(self):

        self.area.setHtml("<p>Carregando comprovante...</p>")
        for bt in (
            self.bt_imprimir, self.bt_baixar,
            self.bt_whatsapp, self.bt_email, self.bt_historico,
        ):
            bt.setEnabled(False)

        rodar_em_thread(
            self,
            _buscar_dados_comprovante,
            self.venda_id,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
        )

    def _ao_carregar_sucesso(self, html):

        for bt in (
            self.bt_imprimir, self.bt_baixar,
            self.bt_whatsapp, self.bt_email, self.bt_historico,
        ):
            bt.setEnabled(True)

        if html is None:
            QMessageBox.critical(
                self, "Erro", "Não foi possível carregar o comprovante."
            )
            self.reject()
            return

        self._html = html
        self.area.setHtml(self._html)

    def _ao_carregar_erro(self, erro):

        for bt in (
            self.bt_imprimir, self.bt_baixar,
            self.bt_whatsapp, self.bt_email, self.bt_historico,
        ):
            bt.setEnabled(True)

        QMessageBox.critical(
            self, "Erro", f"Não foi possível carregar o comprovante.\n{erro}"
        )
        self.reject()

    def imprimir(self):
        comprovante_acoes.imprimir(self.venda_id, self)

    def baixar(self):
        comprovante_acoes.baixar_pdf(self.venda_id, self)

    def enviar_whatsapp(self):
        comprovante_acoes.enviar_whatsapp(self.venda_id, self)

    def enviar_email(self):
        comprovante_acoes.enviar_email(self.venda_id, self)

    def abrir_historico(self):
        HistoricoEnviosDialog(self.venda_id, parent=self).exec()
