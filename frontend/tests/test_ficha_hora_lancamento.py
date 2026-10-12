from datetime import datetime

from PySide6.QtCore import QDate

from telas.ficha_cliente import _dia_com_hora_atual


def test_lancamento_usa_dia_escolhido_com_hora_atual():
    antes = datetime.now().replace(microsecond=0)
    resultado = datetime.fromisoformat(_dia_com_hora_atual(QDate(2026, 10, 11)))
    depois = datetime.now()

    assert resultado.date() == datetime(2026, 10, 11).date()
    assert antes.time() <= resultado.time() <= depois.time()
