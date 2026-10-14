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

import gc
import time

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def _qapp():
    """Uma QApplication só, compartilhada por toda a sessão de teste --
    widgets do Qt não podem ser criados sem uma."""
    app = QApplication.instance() or QApplication([])
    yield app

    # Fecha e destrói as janelas que sobraram ANTES do Python encerrar --
    # sem isso o coletor de lixo destrói widgets do Qt numa ordem
    # qualquer no fim do processo e o pytest pode cair com "fatal
    # exception"/segfault depois de todos os testes já terem passado
    # (aparece conforme quais telas a suíte importa, ex.: contas_pagar).
    for janela in QApplication.topLevelWidgets():
        janela.close()
        janela.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    gc.collect()


@pytest.fixture(autouse=True)
def _valores_visiveis():
    """O app abre com os valores ocultos (olhinho do cabeçalho) -- os
    testes conferem os textos de verdade, então liga a visibilidade."""
    from design.privacidade import privacidade
    privacidade.definir_ocultos(False)
    yield


@pytest.fixture()
def esperar_threads(_qapp):
    """Devolve uma função que bombeia o loop de eventos do Qt até as
    QThread(s) disparadas por rodar_em_thread() (ver services/worker.py)
    terminarem -- necessário porque ao_sucesso/ao_erro/ao_finalizar só
    são entregues de volta na thread principal via fila de eventos, que
    o corpo de um teste nunca roda sozinho (sem app.exec())."""

    def _esperar(objeto, timeout=2.0):
        limite = time.monotonic() + timeout

        while getattr(objeto, "_threads_ativas", None):
            if time.monotonic() > limite:
                raise TimeoutError(
                    "Thread de teste não terminou a tempo "
                    "(ver rodar_em_thread/_threads_ativas)."
                )
            # o sleep cede o GIL de propósito -- sem ele, esse loop
            # bombeia processEvents() sem parar e disputa o GIL com a
            # worker thread, atrasando (as vezes MUITO) o Python dela
            # rodar de verdade em vez de só deixar o Qt entregar o
            # sinal assim que ele chegar.
            time.sleep(0.005)
            _qapp.processEvents()

        # drena qualquer callback que ainda esteja na fila mesmo depois
        # de _threads_ativas esvaziar (a remoção da lista acontece no
        # mesmo processEvents() que entrega os sinais finais).
        _qapp.processEvents()

    return _esperar
