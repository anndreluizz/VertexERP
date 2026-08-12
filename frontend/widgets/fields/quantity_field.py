from PySide6.QtWidgets import QSpinBox


class QuantityField(QSpinBox):

    def __init__(self):
        super().__init__()

        self.setMinimum(0)

        self.setMaximum(999999999)

        self.setMinimumHeight(34)

    @property
    def quantidade(self):

        return int(self.value())

    @quantidade.setter
    def quantidade(self, valor):

        self.setValue(int(valor))