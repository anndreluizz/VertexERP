import os
import sys
import traceback
from datetime import datetime

if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))
    _CAMINHO_LOG_CRASH = os.path.join(
        os.path.dirname(sys.executable), "frontend_log.txt"
    )

    # Build --noconsole: sys.stdout/stderr vêm como None (sem console
    # anexado) — qualquer print() ou traceback não capturado tentaria
    # escrever em None e estouraria AttributeError, matando o processo
    # em silêncio. Precisa de um objeto de arquivo de verdade.
    log_file = open(_CAMINHO_LOG_CRASH, "a", encoding="utf-8", buffering=1)
    sys.stdout = log_file
    sys.stderr = log_file
else:
    _CAMINHO_LOG_CRASH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "frontend_log.txt"
    )


def _instalar_handler_de_crash():
    """Grava qualquer excecao nao tratada (ex.: um bug dentro de um
    callback de tela, ver services/worker.py) no mesmo log do build
    empacotado, com timestamp -- sem isso, o unico rastro de um crash
    era o Visualizador de Eventos do Windows, sem nenhum detalhe do
    que quebrou no codigo Python. NAO cobre crash nativo (violacao de
    acesso, processo morto por falta de memoria) -- nesses casos o
    processo morre antes de qualquer excecao Python ser levantada, e
    o Visualizador de Eventos continua sendo a unica fonte."""

    gancho_padrao = sys.excepthook

    def _gancho(tipo, valor, tb):
        try:
            with open(_CAMINHO_LOG_CRASH, "a", encoding="utf-8") as arquivo:
                arquivo.write(
                    f"\n[{datetime.now().isoformat(timespec='seconds')}] "
                    "Excecao nao tratada:\n"
                )
                traceback.print_exception(tipo, valor, tb, file=arquivo)
        except Exception:
            pass

        gancho_padrao(tipo, valor, tb)

    sys.excepthook = _gancho


_instalar_handler_de_crash()

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from requests.exceptions import RequestException

from design.theme import aplicar_tema
from services import api
from services.api import CertificadoServidorMudou, existe_usuario
from services.preferencias_service import carregar_servidor, carregar_tema_escuro
from telas.login import LoginWindow
from telas.cadastro_inicial import CadastroInicialWindow
from telas.conectar_servidor import ConectarServidorDialog
from telas.principal import PrincipalWindow

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
except (RequestException, CertificadoServidorMudou):

    # Ou esse PC nunca foi configurado (instalação Terminal nova, sem
    # backend local pra conversar), ou o servidor salvo não está
    # respondendo agora, ou o certificado dele mudou (reinstalado) --
    # nos três casos, oferece configurar/corrigir o endereço (a tela
    # tem seu próprio fluxo de "confiar no certificado novo?") antes
    # de desistir. RequestException (não só ConnectionError) porque
    # existe_usuario() agora tem timeout: um servidor que nunca
    # responde (rede lenta, endereço certo mas travado) estoura
    # Timeout, não ConnectionError.
    dialogo = ConectarServidorDialog()

    if dialogo.exec() == QDialog.Accepted and dialogo.confirmado:
        try:
            primeiro_acesso = not existe_usuario()
        except (RequestException, CertificadoServidorMudou):
            _servidor_offline()
    else:
        sys.exit(0)

if primeiro_acesso:
    janela = CadastroInicialWindow()
elif api.retomar_sessao():
    # "Manter conectado" marcado num login anterior -- pula a tela de
    # login direto (ver services/api.py: retomar_sessao/login()).
    janela = PrincipalWindow()
else:
    janela = LoginWindow()

janela.show()

sys.exit(app.exec())
