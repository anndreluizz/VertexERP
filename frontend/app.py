import os
import sys

if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

    # Build --noconsole: sys.stdout/stderr vêm como None (sem console
    # anexado) — qualquer print() ou traceback não capturado tentaria
    # escrever em None e estouraria AttributeError, matando o processo
    # em silêncio. Precisa de um objeto de arquivo de verdade.
    log_path = os.path.join(
        os.path.dirname(sys.executable), "frontend_log.txt"
    )
    log_file = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = log_file
    sys.stderr = log_file

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from requests.exceptions import RequestException

from design.theme import aplicar_tema
from services import api
from services.api import existe_usuario
from services.preferencias_service import carregar_servidor, carregar_tema_escuro
from telas.login import LoginWindow
from telas.cadastro_inicial import CadastroInicialWindow
from telas.conectar_servidor import ConectarServidorDialog

app = QApplication(sys.argv)

# Nome de organização/aplicação usado pelo QSettings (preferencias_service)
# pra resolver onde gravar o .ini de preferências locais.
app.setOrganizationName("VertexERP")
app.setApplicationName("VertexERP")

# aplicar_tema cobre o que o setup manual antigo fazia (Fusion + paleta
# clara/escura, pra nao herdar o tema do Windows) e adiciona a fonte
# Inter e o QSS global do design system por cima. Precisa vir ANTES de
# qualquer tela ser construída (LoginWindow logo abaixo já usa
# tokens.* pra montar seu stylesheet) -- trocar a paleta depois que
# uma tela já existe não re-tinge o que já foi desenhado (ver
# Header._alternar_tema, que reinicia o processo pra aplicar de
# verdade em vez de tentar isso em runtime).
aplicar_tema(app, escuro=carregar_tema_escuro())

# Se esse PC já foi configurado antes como Terminal (ver
# ConectarServidorDialog), usa o endereço salvo em vez do localhost
# padrão — instalação de um PC só nunca tem nada salvo aqui, então
# continua se comportando exatamente como sempre.
endereco_salvo = carregar_servidor()

if endereco_salvo:
    api.definir_url(endereco_salvo)


def _servidor_offline():
    QMessageBox.critical(
        None,
        "Servidor Offline",
        f"Não foi possível conectar ao servidor em {api.URL}.\n\n"
        "Verifique o endereço configurado e se o computador servidor "
        "está ligado e acessível pela rede.",
    )
    sys.exit(1)


try:
    primeiro_acesso = not existe_usuario()
except RequestException:

    # Ou esse PC nunca foi configurado (instalação Terminal nova, sem
    # backend local pra conversar), ou o servidor salvo não está
    # respondendo agora — nos dois casos, oferece configurar/corrigir
    # o endereço antes de desistir. RequestException (não só
    # ConnectionError) porque existe_usuario() agora tem timeout: um
    # servidor que nunca responde (rede lenta, endereço certo mas
    # travado) estoura Timeout, não ConnectionError.
    dialogo = ConectarServidorDialog()

    if dialogo.exec() == QDialog.Accepted and dialogo.confirmado:
        try:
            primeiro_acesso = not existe_usuario()
        except RequestException:
            _servidor_offline()
    else:
        sys.exit(0)

if primeiro_acesso:
    janela = CadastroInicialWindow()
else:
    janela = LoginWindow()

janela.show()

sys.exit(app.exec())
