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

from PySide6.QtWidgets import QApplication, QMessageBox

from requests.exceptions import ConnectionError

from design.theme import aplicar_tema
from services.api import existe_usuario
from telas.login import LoginWindow
from telas.cadastro_inicial import CadastroInicialWindow

app = QApplication(sys.argv)

# aplicar_tema cobre o que o setup manual antigo fazia (Fusion + paleta
# clara, pra nao herdar o tema escuro do Windows) e adiciona a fonte
# Inter e o QSS global do design system por cima.
aplicar_tema(app)

try:
    primeiro_acesso = not existe_usuario()
except ConnectionError:
    QMessageBox.critical(
        None,
        "Servidor Offline",
        "Não foi possível conectar ao Backend.\n\n"
        "Verifique se o FastAPI está executando.",
    )
    sys.exit(1)

if primeiro_acesso:
    janela = CadastroInicialWindow()
else:
    janela = LoginWindow()

janela.show()

sys.exit(app.exec())
