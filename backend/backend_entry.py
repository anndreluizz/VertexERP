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
    # Porta bem incomum de propósito: o fluxo de desenvolvimento (uvicorn
    # rodado manualmente, main:app) usa a porta padrão do uvicorn, 8000 —
    # se o pacote também caísse nessa porta por padrão, rodar o instalador
    # na mesma máquina onde já existe um backend de dev ligado faria o
    # front do pacote conversar com o backend ERRADO (o de dev, com dados
    # reais) sem avisar nada, porque a checagem de "backend pronto" do
    # launcher só confere se ALGUÉM responde na porta, não se é o NOSSO
    # processo.
    porta = int(os.getenv("VERTEXERP_PORT", "58734"))

    # Só aceita conexão de outras máquinas na rede (modo servidor,
    # atendendo caixas em outros PCs) se VERTEXERP_HOST=0.0.0.0 estiver
    # no .env — por padrão continua só-localhost, igual sempre foi.
    host = os.getenv("VERTEXERP_HOST", "127.0.0.1")

    uvicorn.run(app, host=host, port=porta, log_level="info")
