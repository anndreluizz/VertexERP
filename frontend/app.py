import sys
import os

if getattr(sys, "frozen", False):
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

from PySide6.QtWidgets import QApplication

from telas.login import LoginWindow

app = QApplication(sys.argv)

janela = LoginWindow()
janela.show()

sys.exit(app.exec())