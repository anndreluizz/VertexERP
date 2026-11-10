"""Fechar a tela no meio de uma busca em segundo plano derrubava o app
inteiro (0xc0000409, loja 23/10): a QThread era filha da tela e morria
junto, ainda rodando. Roda num processo separado porque, se voltar, o
crash leva o pytest junto."""

import os
import subprocess
import sys
import textwrap

PASTA_FRONTEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCRIPT = textwrap.dedent(
    """
    import time
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QWidget
    from services.worker import rodar_em_thread

    app = QApplication([])

    class Tela(QWidget):
        def ao_sucesso(self, _):
            print("callback em tela fechada")

    tela = Tela()
    rodar_em_thread(tela, time.sleep, 0.5, ao_sucesso=tela.ao_sucesso)
    QTimer.singleShot(50, tela.deleteLater)
    QTimer.singleShot(1500, app.quit)
    app.exec()
    print("sobreviveu")
    """
)


def test_fechar_tela_com_busca_em_andamento_nao_derruba_o_app():
    ambiente = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    resultado = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        cwd=PASTA_FRONTEND,
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "sobreviveu" in resultado.stdout
    assert "callback em tela fechada" not in resultado.stdout


SCRIPT_LIMPEZA = textwrap.dedent(
    """
    import sys, time
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QWidget
    from services import worker

    erros = []
    sys.excepthook = lambda t, e, tb: erros.append(e)
    app = QApplication([])

    class Tela(QWidget):
        def ok(self, _):
            pass

    tela = Tela()
    for i in range(30):
        worker.rodar_em_thread(tela, time.sleep, 0.01 * i, ao_sucesso=tela.ok)
    QTimer.singleShot(2000, app.quit)
    app.exec()
    print("erros", len(erros), "ativas", len(worker._EM_ANDAMENTO))
    """
)


def test_limpeza_da_thread_nao_da_erro_e_solta_tudo():
    # loja 09/11: thread.deleteLater corria antes do wait() em _Limpeza ->
    # RuntimeError a cada 40 s e threads presas em _EM_ANDAMENTO.
    ambiente = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    resultado = subprocess.run(
        [sys.executable, "-c", SCRIPT_LIMPEZA],
        cwd=PASTA_FRONTEND,
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "erros 0 ativas 0" in resultado.stdout, resultado.stdout + resultado.stderr
