"""Nome acessivel automatico, card acionavel por teclado e traducao do Qt."""
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QWidget

from design.theme import aplicar_tema
from widgets.banner import Banner


def _app():
    app = QApplication.instance() or QApplication([])
    if not hasattr(app, "_filtro_nome_acessivel"):
        aplicar_tema(app)
    return app


def test_botao_icone_ganha_nome_do_tooltip():
    app = _app()
    w = QWidget()
    bt = QPushButton(w)
    bt.setToolTip("Notificações")
    w.show()
    app.processEvents()
    assert bt.accessibleName() == "Notificações"


def test_card_aciona_com_enter_e_espaco():
    app = _app()
    banner = Banner("cat", "Titulo", "i", "#123456")
    cliques = []
    banner.clicado.connect(lambda: cliques.append(1))
    assert banner.focusPolicy() == Qt.StrongFocus
    for tecla in (Qt.Key_Return, Qt.Key_Space):
        app.sendEvent(banner, QKeyEvent(QEvent.KeyPress, tecla, Qt.NoModifier))
    assert len(cliques) == 2


def test_botoes_padrao_do_qt_em_portugues():
    _app()
    caixa = QMessageBox()
    caixa.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    assert "Sim" in caixa.button(QMessageBox.Yes).text()


def test_numeros_tabulares_na_fonte_do_app():
    from PySide6.QtGui import QFontMetricsF
    from design.fonts import fonte

    _app()
    m = QFontMetricsF(fonte(20))
    assert m.horizontalAdvance("1111") == m.horizontalAdvance("8888")


def test_menu_do_topo_sem_caractere_de_seta_unicode():
    import inspect
    import design.menu_topo as m

    assert "\u25be" not in inspect.getsource(m)
