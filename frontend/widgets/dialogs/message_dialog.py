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


def perguntar(parent, titulo, texto, sim, nao="Cancelar", padrao_sim=True):
    """Confirmacao com botoes de verbo ("Excluir marca" / "Cancelar") em vez
    de Sim/Nao. Devolve QMessageBox.Yes ou QMessageBox.No, entao quem ja
    comparava com QMessageBox.Yes continua igual. Esc = botao de recusa."""
    # ponto unico de exec(): os testes trocam so _executar
    return _executar(parent, titulo, texto, sim, nao, padrao_sim)


def _executar(parent, titulo, texto, sim, nao, padrao_sim):
    caixa = QMessageBox(QMessageBox.Question, titulo, texto, QMessageBox.NoButton, parent)
    bt_sim = caixa.addButton(sim, QMessageBox.YesRole)
    bt_nao = caixa.addButton(nao, QMessageBox.NoRole)
    caixa.setDefaultButton(bt_sim if padrao_sim else bt_nao)
    caixa.setEscapeButton(bt_nao)
    caixa.exec()
    return QMessageBox.Yes if caixa.clickedButton() is bt_sim else QMessageBox.No
