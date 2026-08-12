import sys
import os

if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

    # Build --noconsole: sys.stdout/stderr vêm como None (sem console
    # anexado). O uvicorn chama sys.stderr.isatty() ao montar o formatter
    # de log padrão — com None isso estoura AttributeError antes de
    # qualquer log ser escrito, matando o processo em silêncio sem deixar
    # rastro nenhum. Precisa de um objeto de arquivo de verdade antes de
    # importar o uvicorn.
    log_path = os.path.join(
        os.path.dirname(sys.executable), "backend_log.txt"
    )
    log_file = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = log_file
    sys.stderr = log_file

import uvicorn

from main import app


if __name__ == "__main__":
    porta = int(os.getenv("VERTEXERP_PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=porta, log_level="info")
