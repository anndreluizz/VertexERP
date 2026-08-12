"""Backup automático do banco Postgres do Vertex ERP.

Roda `pg_dump` lendo as credenciais de `backend/.env`, salva um .sql
em Documentos/VertexERP/Backups e apaga backups com mais de 30 dias.

Uso manual: `python scripts/backup_db.py`
"""

import ctypes.wintypes
import glob
import os
import subprocess
from datetime import datetime, timedelta

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Duas formas de instalação coexistem: a portátil (tudo autocontido, .env
# na raiz) e a manual (Python/Postgres instalados à parte, .env em
# backend/). Tenta a raiz primeiro, cai pro backend/ se não achar.
ENV_PATH_RAIZ = os.path.join(BASE_DIR, ".env")
ENV_PATH_BACKEND = os.path.join(BASE_DIR, "backend", ".env")
ENV_PATH = ENV_PATH_RAIZ if os.path.exists(ENV_PATH_RAIZ) else ENV_PATH_BACKEND

load_dotenv(ENV_PATH)

DIAS_PARA_MANTER = 30


def localizar_pg_dump():
    """pg_dump.exe não está no PATH por padrão. Procura primeiro no
    Postgres portátil (instalação autocontida, sem instalador) e depois
    na instalação padrão do Postgres no Windows, testando qualquer
    versão instalada."""

    portatil = os.path.join(
        BASE_DIR, "postgres-portable", "bin", "pg_dump.exe"
    )

    if os.path.exists(portatil):
        return portatil

    candidatos = glob.glob(
        r"C:\Program Files\PostgreSQL\*\bin\pg_dump.exe"
    )

    if not candidatos:
        raise FileNotFoundError(
            "pg_dump.exe não encontrado nem em postgres-portable\\bin\\, "
            "nem em C:\\Program Files\\PostgreSQL\\*\\bin\\. "
            "O PostgreSQL está instalado nesse computador?"
        )

    # Se tiver mais de uma versão instalada, usa a mais recente.
    return sorted(candidatos)[-1]


def pasta_documentos():
    """Resolve a pasta Documentos de verdade — no Windows, ela costuma
    estar redirecionada pro OneDrive, então não dá pra só concatenar
    o caminho do usuário na mão."""

    CSIDL_PERSONAL = 5
    SHGFP_TYPE_CURRENT = 0

    buffer = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)

    ctypes.windll.shell32.SHGetFolderPathW(
        None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buffer
    )

    return buffer.value


def pasta_backups():
    caminho = os.path.join(pasta_documentos(), "VertexERP", "Backups")
    os.makedirs(caminho, exist_ok=True)
    return caminho


def fazer_backup():
    destino = pasta_backups()

    agora = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    arquivo = os.path.join(destino, f"vertexerp_{agora}.sql")

    ambiente = os.environ.copy()
    ambiente["PGPASSWORD"] = os.getenv("DB_PASSWORD", "")

    comando = [
        localizar_pg_dump(),
        "-h", os.getenv("DB_HOST", "localhost"),
        "-p", os.getenv("DB_PORT", "5432"),
        "-U", os.getenv("DB_USER", "postgres"),
        "-F", "p",
        "-f", arquivo,
        os.getenv("DB_NAME", "vertexerp"),
    ]

    resultado = subprocess.run(
        comando,
        env=ambiente,
        capture_output=True,
        text=True,
    )

    if resultado.returncode != 0:
        raise RuntimeError(f"pg_dump falhou:\n{resultado.stderr}")

    return arquivo


def limpar_backups_antigos():
    destino = pasta_backups()
    limite = datetime.now() - timedelta(days=DIAS_PARA_MANTER)

    removidos = []

    for nome in os.listdir(destino):
        if not nome.endswith(".sql"):
            continue

        caminho = os.path.join(destino, nome)
        modificado = datetime.fromtimestamp(os.path.getmtime(caminho))

        if modificado < limite:
            os.remove(caminho)
            removidos.append(nome)

    return removidos


def main():
    arquivo = fazer_backup()
    print(f"Backup criado: {arquivo}")

    removidos = limpar_backups_antigos()

    if removidos:
        print(f"Backups antigos removidos ({len(removidos)}): {', '.join(removidos)}")


if __name__ == "__main__":
    main()
