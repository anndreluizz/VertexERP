from PySide6.QtWidgets import QAbstractSpinBox, QDoubleSpinBox


class MoneyField(QDoubleSpinBox):

    def __init__(self):
        super().__init__()

        self.setDecimals(2)

        self.setMaximum(999999999.99)

        self.setMinimum(0)

        self.setSingleStep(1)

        self.setPrefix("R$ ")

        # valor se digita: sem as setinhas de subir/descer
        self.setButtonSymbols(QAbstractSpinBox.NoButtons)

        self.setMinimumHeight(34)

    @property
    def valor(self):

        return float(self.value())

    @valor.setter
    def valor(self, valor):

        self.setValue(float(valor))