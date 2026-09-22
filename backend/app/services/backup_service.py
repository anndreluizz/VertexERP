import ctypes
import ctypes.wintypes
import os
import subprocess
from datetime import datetime

CREATE_NO_WINDOW = 0x08000000


def _pasta_documentos():
    """Mesma resolucao de launcher.py::_pasta_documentos -- duplicada
    de proposito (launcher.py e' um script standalone, empacotado
    separado do backend, nao um pacote importavel daqui) pra ler/
    escrever na MESMA pasta que o backup automatico diario ja usa."""

    CSIDL_PERSONAL = 5
    SHGFP_TYPE_CURRENT = 0

    buffer = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)

    ctypes.windll.shell32.SHGetFolderPathW(
        None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buffer
    )

    return buffer.value


def _pasta_backups():
    caminho = os.path.join(_pasta_documentos(), "VertexERP", "Backups")
    os.makedirs(caminho, exist_ok=True)
    return caminho


def _caminho_pg_dump():
    """No instalador empacotado, o backend roda como subprocesso do
    launcher (ver launcher.py::ambiente_para_subprocessos), que injeta
    VERTEXERP_INSTALL_DIR -- o Postgres portatil fica em
    <instalacao>/postgres-portable/bin/. Em dev (sem instalador), cai
    pro pg_dump do PATH (Postgres instalado normalmente na maquina)."""

    instalacao = os.getenv("VERTEXERP_INSTALL_DIR")

    if instalacao:
        caminho_portatil = os.path.join(
            instalacao, "postgres-portable", "bin", "pg_dump.exe"
        )
        if os.path.exists(caminho_portatil):
            return caminho_portatil

    return "pg_dump"


class BackupService:

    @staticmethod
    def pasta_backups():
        return _pasta_backups()

    @staticmethod
    def listar():

        pasta = _pasta_backups()

        arquivos = []

        for nome in os.listdir(pasta):

            if not nome.endswith(".sql"):
                continue

            caminho = os.path.join(pasta, nome)
            info = os.stat(caminho)

            arquivos.append({
                "nome": nome,
                "tamanho_bytes": info.st_size,
                "criado_em": datetime.fromtimestamp(info.st_mtime),
            })

        return sorted(arquivos, key=lambda a: a["criado_em"], reverse=True)

    @staticmethod
    def criar_manual():
        """pg_dump direto (protocolo Postgres, nao passa pelo
        SQLAlchemy) -- mesmo comando que launcher.py::_fazer_backup
        roda automaticamente todo dia, so' que disparado na hora pelo
        usuario em vez de pelo timer."""

        pasta = _pasta_backups()

        agora = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        nome_arquivo = f"vertexerp_{agora}.sql"
        caminho = os.path.join(pasta, nome_arquivo)

        ambiente = os.environ.copy()
        ambiente["PGPASSWORD"] = os.getenv("DB_PASSWORD", "")

        resultado = subprocess.run(
            [
                _caminho_pg_dump(),
                "-h", os.getenv("DB_HOST", "127.0.0.1"),
                "-p", os.getenv("DB_PORT", "5432"),
                "-U", os.getenv("DB_USER", "postgres"),
                "-F", "p",
                "-f", caminho,
                os.getenv("DB_NAME", "vertexerp"),
            ],
            capture_output=True,
            text=True,
            env=ambiente,
            creationflags=CREATE_NO_WINDOW,
        )

        if resultado.returncode != 0:
            raise Exception(f"pg_dump falhou: {resultado.stderr}")

        info = os.stat(caminho)

        return {
            "nome": nome_arquivo,
            "tamanho_bytes": info.st_size,
            "criado_em": datetime.fromtimestamp(info.st_mtime),
        }
