from PySide6.QtWidgets import QMessageBox


class Mensagem:

    @staticmethod
    def sucesso(parent, texto):

        QMessageBox.information(
            parent,
            "Sucesso",
            texto,
        )

    @staticmethod
    def erro(parent, texto):

        QMessageBox.critical(
            parent,
            "Erro",
            texto,
        )

    @staticmethod
    def aviso(parent, texto):

        QMessageBox.warning(
            parent,
            "Aviso",
            texto,
        )

    @staticmethod
    def confirmar(
        parent,
        texto,
    ):

        resposta = QMessageBox.question(
            parent,
            "Confirmação",
            texto,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        return resposta == QMessageBox.Yes