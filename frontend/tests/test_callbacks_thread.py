"""rodar_em_thread recusa lambda em ao_sucesso/ao_erro/ao_finalizar (erro do Caixa em 17/11)."""
import re
from pathlib import Path

def test_nenhuma_lambda_em_callback_de_thread():
    raiz = Path(__file__).resolve().parent.parent
    ruins = [
        f"{p.relative_to(raiz)}:{n}"
        for p in raiz.glob("telas/**/*.py")
        for n, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"\bao_(sucesso|erro|finalizar)\s*=\s*lambda", linha)
    ]
    assert not ruins, ruins
