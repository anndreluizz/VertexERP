import ctypes
import ctypes.wintypes
import json
import os
import subprocess
import threading
import time
import traceback
from datetime import datetime, timedelta

CREATE_NO_WINDOW = 0x08000000

# Escrito pelo launcher.py a cada tentativa de backup automatico (ver
# launcher.py::_loop_backup_diario) -- mesmo nome dos dois lados.
ARQUIVO_STATUS = "status_backup.json"

# O launcher faz backup na abertura e a cada 4h; passar disso sem
# nenhum arquivo novo significa que o automatico parou de rodar.
HORAS_SEM_BACKUP_PARA_ALERTA = 24


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


_RODAPE_DUMP = b"PostgreSQL database dump complete"


def validar_dump(caminho):
    """Mesma checagem de launcher.py::_validar_dump (duplicada pelo
    mesmo motivo de _pasta_documentos): arquivo nao vazio e com o
    rodape que o pg_dump so escreve quando termina de verdade."""

    tamanho = os.path.getsize(caminho)

    if tamanho == 0:
        raise Exception("pg_dump gerou um arquivo vazio.")

    with open(caminho, "rb") as arquivo:
        arquivo.seek(max(0, tamanho - 4096))
        final = arquivo.read()

    if _RODAPE_DUMP not in final:
        raise Exception(
            "O arquivo de backup ficou incompleto (sem o rodape do "
            "pg_dump) e foi descartado."
        )


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
    def _ler_status():
        """None quando o arquivo nao existe -- backend rodando sem o
        launcher (dev), onde nao ha backup automatico nenhum."""

        caminho = os.path.join(_pasta_backups(), ARQUIVO_STATUS)

        try:
            with open(caminho, encoding="utf-8") as arquivo:
                return json.load(arquivo)
        except (OSError, ValueError):
            return None

    @staticmethod
    def alerta(itens, status, agora=None):
        """Mensagem pro admin quando o backup nao esta protegendo a loja
        direito, ou None se esta tudo certo. Ordem = gravidade: falha
        total primeiro, depois backup parado, depois so' a copia fora
        do PC -- que parece detalhe, mas foi a falta dela que fez a
        loja perder tudo quando o PC-Servidor foi formatado (issue #4)."""

        agora = agora or datetime.now()
        status = status or {}

        if status.get("erro"):
            return f"O último backup automático falhou: {status['erro']}"

        if not itens:
            return "Nenhum backup do banco de dados foi encontrado."

        horas = (agora - itens[0]["criado_em"]) / timedelta(hours=1)
        if horas > HORAS_SEM_BACKUP_PARA_ALERTA:
            dias = int(horas // 24)
            return (
                f"O último backup foi há {dias} dia(s). "
                "O backup automático pode ter parado."
            )

        if not status:
            return None

        if status.get("erro_copia_externa"):
            return (
                "O backup foi salvo neste PC, mas a cópia para "
                f"{status.get('copia_externa')} falhou: "
                f"{status['erro_copia_externa']}"
            )

        if not status.get("copia_externa"):
            return (
                "Os backups estão guardados só neste PC. Se ele "
                "estragar, os dados se perdem. Configure "
                "VERTEXERP_BACKUP_EXTRA no .env do Servidor com uma "
                "pasta do OneDrive ou Google Drive."
            )

        return None

    @staticmethod
    def resumo():
        itens = BackupService.listar()
        status = BackupService._ler_status()

        return {
            "itens": itens,
            "pasta": _pasta_backups(),
            "copia_externa": (status or {}).get("copia_externa"),
            "alerta": BackupService.alerta(itens, status),
        }

    @staticmethod
    def criar_manual():
        """pg_dump direto (protocolo Postgres, nao passa pelo
        SQLAlchemy) -- mesmo comando que launcher.py::_fazer_backup
        roda automaticamente a cada 4h, so' que disparado na hora pelo
        usuario em vez de pelo timer."""

        pasta = _pasta_backups()

        agora = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        nome_arquivo = f"vertexerp_{agora}.sql"
        caminho = os.path.join(pasta, nome_arquivo)

        ambiente = os.environ.copy()
        ambiente["PGPASSWORD"] = os.getenv("DB_PASSWORD", "")

        # .tmp + validacao + rename -- mesmo motivo de
        # launcher.py::_fazer_backup: um dump cortado no meio nunca
        # pode aparecer na pasta como se fosse um backup bom
        temporario = caminho + ".tmp"

        try:
            resultado = subprocess.run(
                [
                    _caminho_pg_dump(),
                    "-h", os.getenv("DB_HOST", "127.0.0.1"),
                    "-p", os.getenv("DB_PORT", "5432"),
                    "-U", os.getenv("DB_USER", "postgres"),
                    "-F", "p",
                    "-f", temporario,
                    os.getenv("DB_NAME", "vertexerp"),
                ],
                capture_output=True,
                text=True,
                env=ambiente,
                creationflags=CREATE_NO_WINDOW,
            )

            if resultado.returncode != 0:
                raise Exception(f"pg_dump falhou: {resultado.stderr}")

            validar_dump(temporario)
            os.replace(temporario, caminho)

        finally:
            if os.path.exists(temporario):
                os.remove(temporario)

        info = os.stat(caminho)

        return {
            "nome": nome_arquivo,
            "tamanho_bytes": info.st_size,
            "criado_em": datetime.fromtimestamp(info.st_mtime),
        }


# ==========================================
# AVISO NO CELULAR -- a faixa amarela do desktop so' aparece pra admin
# logado no desktop; o PC-Servidor passa dias sem ninguem logado, e foi
# assim que a loja ficou 3 semanas sem backup sem ninguem saber.
# ==========================================

_INTERVALO_CHECAGEM_SEGUNDOS = 60 * 60

# mesmo alerta persistindo: repete no maximo 1x por dia (senao vira
# ruido que o dono aprende a ignorar)
_REPETIR_MESMO_AVISO = timedelta(hours=24)


def deve_avisar(alerta, ultimo_alerta, ultimo_envio, agora):
    if not alerta:
        return False

    if alerta != ultimo_alerta or ultimo_envio is None:
        return True

    return agora - ultimo_envio >= _REPETIR_MESMO_AVISO


def _loop_aviso_backup():
    from app.database.session import SessionLocal
    from app.services.notificacao_service import NotificacaoService

    ultimo_alerta = None
    ultimo_envio = None

    while True:
        # primeira checagem so' depois de 1h: da tempo do backup que o
        # launcher faz na abertura terminar e gravar o status
        time.sleep(_INTERVALO_CHECAGEM_SEGUNDOS)

        try:
            resumo = BackupService.resumo()
            alerta = resumo["alerta"]
            agora = datetime.now()

            if deve_avisar(alerta, ultimo_alerta, ultimo_envio, agora):
                db = SessionLocal()
                try:
                    NotificacaoService.enviar_para_admins(
                        db, "Backup com problema", alerta
                    )
                finally:
                    db.close()

                ultimo_envio = agora

            ultimo_alerta = alerta

        except Exception:
            traceback.print_exc()


def iniciar_aviso_backup():
    """Chamado no startup (ver main.py). So' roda na instalacao de
    verdade (backend subido pelo launcher, que e' quem faz o backup
    automatico) -- em dev nao ha backup nenhum pra vigiar."""

    if not os.getenv("VERTEXERP_INSTALL_DIR"):
        return

    threading.Thread(target=_loop_aviso_backup, daemon=True).start()
