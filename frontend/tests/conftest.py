"""Config compartilhada dos testes do frontend -- roda tudo com o
Qt em modo offscreen (sem precisar de tela de verdade) e garante que
os módulos do app (services/, telas/, design/...) sejam importáveis
mesmo rodando o pytest de fora da pasta frontend/."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_RAIZ_FRONTEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ_FRONTEND not in sys.path:
    sys.path.insert(0, _RAIZ_FRONTEND)

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def _qapp():
    """Uma QApplication só, compartilhada por toda a sessão de teste --
    widgets do Qt não podem ser criados sem uma."""
    app = QApplication.instance() or QApplication([])
    yield app
