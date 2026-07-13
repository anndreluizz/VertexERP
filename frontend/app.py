import sys

from PySide6.QtWidgets import QApplication

from telas.login import LoginWindow

app = QApplication(sys.argv)

janela = LoginWindow()
janela.show()

sys.exit(app.exec())