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
from PySide6.QtGui import QPalette, QColor

from requests.exceptions import ConnectionError

from services.api import existe_usuario
from telas.login import LoginWindow
from telas.cadastro_inicial import CadastroInicialWindow

app = QApplication(sys.argv)

# Forca um tema claro consistente. Sem isso, no Windows com modo escuro
# ativado, o Qt usa paleta escura (texto claro) por padrao — e como as
# telas do sistema usam fundo branco fixo, o texto de widgets padrao
# (QMessageBox, QInputDialog, QLabel sem cor propria) fica invisivel
# (texto claro em cima de fundo claro).
app.setStyle("Fusion")

paleta = QPalette()
paleta.setColor(QPalette.Window, QColor("#f4f5f7"))
paleta.setColor(QPalette.WindowText, QColor("#202225"))
paleta.setColor(QPalette.Base, QColor("#ffffff"))
paleta.setColor(QPalette.AlternateBase, QColor("#f4f5f7"))
paleta.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
paleta.setColor(QPalette.ToolTipText, QColor("#202225"))
paleta.setColor(QPalette.Text, QColor("#202225"))
paleta.setColor(QPalette.Button, QColor("#f4f5f7"))
paleta.setColor(QPalette.ButtonText, QColor("#202225"))
paleta.setColor(QPalette.Highlight, QColor("#1565C0"))
paleta.setColor(QPalette.HighlightedText, QColor("#ffffff"))
paleta.setColor(QPalette.PlaceholderText, QColor("#9e9e9e"))
paleta.setColor(
    QPalette.Disabled, QPalette.Text, QColor("#9e9e9e")
)
paleta.setColor(
    QPalette.Disabled, QPalette.WindowText, QColor("#9e9e9e")
)

app.setPalette(paleta)

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
