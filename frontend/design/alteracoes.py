"""Aviso antes de fechar um formulario com alteracoes nao salvas.

Uso: `class MeuDialog(ProtegeAlteracoes, DialogoPadrao)`. Conta so o que a
PESSOA mexeu (textEdited, activated, clicked...): carga de dados que chega
depois, por thread, nao conta. Salvar usa accept(), que passa direto."""

from PySide6.QtWidgets import (
    QMessageBox, QAbstractButton, QComboBox, QDateTimeEdit, QDoubleSpinBox, QLineEdit,
    QPlainTextEdit, QSpinBox, QTextEdit,
)

from widgets.dialogs.message_dialog import perguntar


class ProtegeAlteracoes:

    _alteracoes = False
    _sinais_ligados = False

    def showEvent(self, evento):
        super().showEvent(evento)
        if not self._sinais_ligados:
            self._sinais_ligados = True
            self._ligar_sinais()

    def _marcar(self, *_):
        self._alteracoes = True

    def _ligar_sinais(self):
        for w in self.findChildren(QLineEdit):
            w.textEdited.connect(self._marcar)
        for w in self.findChildren(QComboBox):
            w.activated.connect(self._marcar)
        for w in self.findChildren(QAbstractButton):
            if w.isCheckable():
                w.clicked.connect(self._marcar)
        # editingFinished dispara so de passar o Tab: conta valor mudado COM foco
        for classe, sinal in ((QSpinBox, "valueChanged"), (QDoubleSpinBox, "valueChanged"),
                              (QDateTimeEdit, "dateTimeChanged")):
            for w in self.findChildren(classe):
                getattr(w, sinal).connect(lambda *_, w=w: self._marcar() if w.hasFocus() else None)
        # texto longo nao tem sinal "so usuario": teclas no viewport
        for w in self.findChildren(QTextEdit) + self.findChildren(QPlainTextEdit):
            w.textChanged.connect(lambda w=w: self._marcar() if w.hasFocus() else None)

    def reject(self):
        if self._alteracoes and perguntar(
            self, "Alterações não salvas",
            "Você mudou dados e ainda não salvou.\n\nSair mesmo assim e perder as alterações?",
            sim="Sair sem salvar", nao="Continuar editando", padrao_sim=False,
        ) != QMessageBox.Yes:
            return
        super().reject()
