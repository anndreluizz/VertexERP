import ctypes
import ctypes.wintypes
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta

if getattr(sys, "frozen", False):
    # Empacotado pelo PyInstaller: __file__ aponta pra uma pasta temporária
    # de extração, não pra onde o .exe realmente está — precisa usar
    # sys.executable pra achar os outros .exe/pastas como irmãos.
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --onedir (não --onefile): o programa já fica descompactado em disco,
# sem re-extrair tudo pra uma pasta temporária a cada abertura — isso
# evita o antivírus escanear centenas de arquivos toda vez que o
# sistema é aberto, que é o que deixava a inicialização extremamente
# lenta num PC mais fraco.
BACKEND_EXE = os.path.join(
    BASE_DIR, "VertexERP-Backend", "VertexERP-Backend.exe"
)
FRONTEND_EXE = os.path.join(
    BASE_DIR, "VertexERP-Frontend", "VertexERP-Frontend.exe"
)

PG_DIR = os.path.join(BASE_DIR, "postgres-portable")
PG_BIN = os.path.join(PG_DIR, "bin")
PG_DATA = os.path.join(BASE_DIR, "pgdata")
PG_LOG = os.path.join(BASE_DIR, "pgdata_log.txt")

# Porta não-padrão de propósito: evita conflito se a máquina já tiver um
# Postgres "de verdade" instalado escutando na 5432 por outro motivo. Usa uma
# porta pouco comum (não 5433) porque essa já colide com o container Docker
# de outro projeto (vertexlanchonete-postgres) numa das máquinas de teste.
PG_PORT = "5442"
PG_SUPERUSER = "postgres"
PG_SUPERSENHA = "Vertex2026"
PG_BANCO = "vertexerp"

LOCK_FILE = os.path.join(BASE_DIR, ".vertexerp.lock")

CREATE_NO_WINDOW = 0x08000000


def caminho_tem_caractere_nao_ascii():
    """O initdb desse Postgres portátil quebra (erro de encoding UTF-8
    interno) quando o caminho de instalação tem letra acentuada — e
    "Área de Trabalho" é justamente o nome padrão da Área de Trabalho
    em qualquer Windows em português, então é fácil o cliente cair
    exatamente nessa armadilha sem querer. Detecta isso ANTES de tentar
    subir o Postgres, pra mostrar um aviso claro em vez de um erro
    cripto vindo de dentro do initdb."""

    try:
        BASE_DIR.encode("ascii")
        return False
    except UnicodeEncodeError:
        return True


def ambiente_para_subprocessos():
    """O launcher também é um pacote PyInstaller — carrega variáveis de
    ambiente internas (_PYI_ARCHIVE_FILE, _PYI_APPLICATION_HOME_DIR,
    _PYI_PARENT_PROCESS_LEVEL) que apontam pro PRÓPRIO .exe dele.
    Backend e frontend são pacotes PyInstaller SEPARADOS — se herdam
    essas variáveis por padrão (comportamento normal de subprocess),
    o bootloader de cada um se confunde tentando usar o arquivo/nível
    errado, e o processo trava silenciosamente sem nunca terminar de
    subir. Cada subprocesso precisa começar sem essas variáveis, pra
    seu próprio bootloader se inicializar do zero corretamente."""

    env = os.environ.copy()

    for chave in list(env):
        if chave.startswith("_PYI_"):
            del env[chave]

    # O backend roda de dentro de VertexERP-Backend/, uma subpasta — sem
    # isso ele acha que a raiz da instalação é essa subpasta, e escreve
    # PRIMEIRO_ACESSO.txt lá dentro em vez de do lado do VertexERP.exe.
    env["VERTEXERP_INSTALL_DIR"] = BASE_DIR

    return env


def processo_existe(pid):
    """Confere se um PID ainda está vivo no Windows via tasklist —
    os.kill(pid, 0) não é confiável nessa plataforma."""

    resultado = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}"],
        capture_output=True,
        text=True,
    )

    return str(pid) in resultado.stdout


def _criar_trava():
    """Cria o arquivo de trava de forma atômica (O_CREAT|O_EXCL): se dois
    processos tentarem ao mesmo tempo, só um consegue — evita a corrida
    de checar "existe?" e escrever em passos separados."""

    descritor = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(descritor, str(os.getpid()).encode())
    os.close(descritor)


def obter_trava():
    """Garante que só uma instância do sistema fique aberta por vez —
    se o usuário clicar duas vezes no ícone, a segunda simplesmente não
    abre outro backend/PDV por cima do primeiro."""

    try:
        _criar_trava()
        return True
    except FileExistsError:
        pass

    try:
        with open(LOCK_FILE) as arquivo:
            pid = int(arquivo.read().strip())
    except (ValueError, OSError):
        pid = None

    if pid is not None and processo_existe(pid):
        return False

    # Trava órfã (a instância anterior morreu sem limpar) — refaz.
    try:
        os.remove(LOCK_FILE)
    except OSError:
        pass

    try:
        _criar_trava()
        return True
    except FileExistsError:
        return False


# ==========================================
# POSTGRES PORTÁTIL
# ==========================================

def _nosso_postgres_ja_rodando():
    """Confere se É O NOSSO cluster (PG_DATA) que já está de pé, perguntando
    diretamente pro pg_ctl — não só se a porta está aberta.

    Checar só a porta é frágil: qualquer outro serviço na máquina (ex.: um
    container Docker de outro projeto) pode estar escutando nela por
    coincidência, e aí a gente erroneamente concluiria "nosso Postgres já
    subiu" e nunca chamaria pg_ctl start — só pra descobrir depois, ao tentar
    autenticar, que quem respondeu na porta era um Postgres totalmente
    diferente, com credenciais diferentes."""

    resultado = subprocess.run(
        [
            os.path.join(PG_BIN, "pg_ctl.exe"),
            "-D", PG_DATA,
            "status",
        ],
        capture_output=True,
        creationflags=CREATE_NO_WINDOW,
    )

    return resultado.returncode == 0


def _banco_ja_inicializado():
    # initdb cria esse arquivo como marca de "cluster já criado".
    return os.path.exists(os.path.join(PG_DATA, "PG_VERSION"))


def inicializar_cluster_se_necessario():
    if _banco_ja_inicializado():
        return

    os.makedirs(PG_DATA, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False
    ) as arquivo_senha:
        arquivo_senha.write(PG_SUPERSENHA)
        caminho_senha = arquivo_senha.name

    try:
        subprocess.run(
            [
                os.path.join(PG_BIN, "initdb.exe"),
                "-D", PG_DATA,
                "-U", PG_SUPERUSER,
                "--pwfile", caminho_senha,
                "-E", "UTF8",
                "--locale=C",
            ],
            check=True,
            creationflags=CREATE_NO_WINDOW,
        )
    finally:
        os.remove(caminho_senha)


def iniciar_postgres():
    if _nosso_postgres_ja_rodando():
        # É o nosso próprio cluster que já está de pé (ex.: sessão anterior
        # não finalizada direito) — reaproveita em vez de subir outro.
        return

    subprocess.run(
        [
            os.path.join(PG_BIN, "pg_ctl.exe"),
            "-D", PG_DATA,
            "-l", PG_LOG,
            "-o", f"-p {PG_PORT}",
            "-w",
            "start",
        ],
        check=True,
        creationflags=CREATE_NO_WINDOW,
    )


def parar_postgres():
    subprocess.run(
        [
            os.path.join(PG_BIN, "pg_ctl.exe"),
            "-D", PG_DATA,
            "-m", "fast",
            "stop",
        ],
        creationflags=CREATE_NO_WINDOW,
    )


def garantir_banco_vertexerp():
    env = os.environ.copy()
    env["PGPASSWORD"] = PG_SUPERSENHA

    resultado = subprocess.run(
        [
            os.path.join(PG_BIN, "psql.exe"),
            "-U", PG_SUPERUSER,
            "-h", "127.0.0.1",
            "-p", PG_PORT,
            "-lqt",
        ],
        capture_output=True,
        text=True,
        env=env,
        creationflags=CREATE_NO_WINDOW,
    )

    if PG_BANCO in resultado.stdout:
        return

    subprocess.run(
        [
            os.path.join(PG_BIN, "createdb.exe"),
            "-U", PG_SUPERUSER,
            "-h", "127.0.0.1",
            "-p", PG_PORT,
            PG_BANCO,
        ],
        check=True,
        env=env,
        creationflags=CREATE_NO_WINDOW,
    )


def _perguntar_sim_nao(titulo, mensagem):
    # MB_YESNO (0x4) | MB_ICONQUESTION (0x20); IDYES == 6
    resposta = ctypes.windll.user32.MessageBoxW(
        None, mensagem, titulo, 0x4 | 0x20
    )
    return resposta == 6


def garantir_env():
    """Gera o backend/.env (na raiz da instalação) apontando pro Postgres
    portátil, se ainda não existir — não sobrescreve um .env que o usuário
    já tenha configurado manualmente.

    Só roda uma vez por instalação (a próxima abertura já encontra o
    .env pronto), então é o momento certo pra perguntar se esse PC vai
    servir de "servidor" pros outros caixas da loja."""

    caminho_env = os.path.join(BASE_DIR, ".env")

    if os.path.exists(caminho_env):
        return

    modo_servidor = _perguntar_sim_nao(
        "Modo Servidor",
        "Este PC vai funcionar como Servidor pros outros caixas da loja?\n\n"
        "Escolha Sim se outros computadores vão se conectar a este aqui "
        "pra dividir o mesmo estoque, clientes e vendas.\n\n"
        "Escolha Não se este vai ser o único PC (ou um caixa que se conecta "
        "a outro servidor) — pode mudar isso depois editando o arquivo "
        ".env, se precisar.",
    )

    host = "0.0.0.0" if modo_servidor else "127.0.0.1"

    # Chave só desse install, gerada na hora — nunca a mesma em duas
    # instalações diferentes (ver auth/jwt.py: sem isso, qualquer
    # instalação aceitaria token assinado por qualquer outra).
    chave_secreta = secrets.token_hex(32)

    with open(caminho_env, "w", encoding="utf-8") as arquivo:
        arquivo.write(
            "APP_NAME=Vertex ERP\n"
            "APP_VERSION=1.0.0\n\n"
            "DB_HOST=127.0.0.1\n"
            f"DB_PORT={PG_PORT}\n"
            f"DB_NAME={PG_BANCO}\n"
            f"DB_USER={PG_SUPERUSER}\n"
            f"DB_PASSWORD={PG_SUPERSENHA}\n\n"
            f"VERTEXERP_HOST={host}\n\n"
            f"SECRET_KEY={chave_secreta}\n"
            "JWT_ALGORITHM=HS256\n"
            "ACCESS_TOKEN_EXPIRE_MINUTES=60\n"
        )


# ==========================================
# BACKEND / FRONTEND
# ==========================================

def backend_pronto():
    import ssl
    import urllib.request

    # Tem que bater com o padrao de backend/backend_entry.py e
    # frontend/services/api.py (58734) — ver comentario lá pra entender
    # por que nao pode ser 8000.
    porta = os.getenv("VERTEXERP_PORT", "58734")

    # o backend agora serve HTTPS com certificado autoassinado (ver
    # app/core/tls.py) -- essa checagem roda na mesma maquina que
    # acabou de subir o proprio backend, entao nao ha nada a ganhar
    # verificando a identidade dele contra si mesmo aqui.
    contexto = ssl.create_default_context()
    contexto.check_hostname = False
    contexto.verify_mode = ssl.CERT_NONE

    try:
        urllib.request.urlopen(
            f"https://127.0.0.1:{porta}/docs", timeout=3, context=contexto
        )
        return True
    except Exception:
        return False


def iniciar_backend():
    # Não reaproveita um backend "já rodando" na 8000 — a trava de
    # instância única (obter_trava) já garante que só existe um Vertex
    # ERP por vez, e confiar numa checagem de porta cria corrida: um
    # processo antigo ainda liberando a porta pode enganar essa checagem
    # e deixar o launcher sem nenhum backend de verdade rodando.
    processo = subprocess.Popen(
        [BACKEND_EXE],
        cwd=BASE_DIR,
        creationflags=CREATE_NO_WINDOW,
        env=ambiente_para_subprocessos(),
    )

    # 15 minutos: na primeira vez (banco vazio) o backend precisa
    # descompactar a si mesmo, rodar toda a cadeia de migrações e criar o
    # admin — num PC fraco/antigo (o cenário que esse empacotamento
    # inteiro existe pra resolver) isso pode legitimamente demorar bem
    # mais que os ~10s que leva numa máquina rápida. Em testes reais, disco
    # sob contenção (antivírus, outros programas) fez um checkpoint do
    # Postgres sozinho levar mais de 100s — 5 minutos não era margem
    # suficiente nesses casos.
    for _ in range(900):
        if backend_pronto():
            return processo
        time.sleep(1)

    # Não travou, mas não subiu — não adianta abrir o frontend pra só
    # mostrar "Servidor Offline". Mata o que tentou subir e desiste.
    encerrar_processo(BACKEND_EXE)
    return None


def iniciar_frontend():
    return subprocess.Popen(
        [FRONTEND_EXE],
        cwd=BASE_DIR,
        env=ambiente_para_subprocessos(),
    )


def encerrar_processo(caminho_exe):
    """Mata pelo nome da imagem (taskkill /IM), não pelo PID.

    O bootloader do PyInstaller (onefile ou onedir) roda o código de
    verdade num processo filho — se esse pai já morreu sozinho antes da
    gente tentar encerrar (comum, acontece rápido), um "taskkill /T
    /PID <pai>" não acha mais os filhos pra matar, e o processo real
    sobrevive órfão. Matar pelo nome do executável (só existe uma
    instância por vez, graças à trava) sempre acha o processo de
    verdade, não importa a relação pai/filho no momento."""

    subprocess.run(
        ["taskkill", "/F", "/IM", os.path.basename(caminho_exe)],
        capture_output=True,
        creationflags=CREATE_NO_WINDOW,
    )


# ==========================================
# BACKUP AUTOMÁTICO
# ==========================================

DIAS_PARA_MANTER_BACKUP = 30

# 24h -- roda uma vez por dia (a primeira já quase na hora de abrir),
# nao precisa de nada mais fino que isso pra um backup de loja.
_INTERVALO_BACKUP_SEGUNDOS = 24 * 60 * 60


def _pasta_documentos():
    """Resolve a pasta Documentos de verdade -- no Windows ela costuma
    estar redirecionada pro OneDrive, entao nao da pra so concatenar
    o caminho do usuario na mao."""

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


def _ler_env(chave):
    """Le uma variavel do .env que o proprio launcher.py escreve (ver
    garantir_env()) -- launcher.py nunca carrega o .env pro proprio
    os.environ (só o backend consome ele, no subprocess dele), entao
    pra ler uma configuracao opcional aqui precisa parsear o arquivo
    na mao. Devolve None se o arquivo nao existir ou a chave nao
    estiver la (ou estiver vazia)."""

    caminho_env = os.path.join(BASE_DIR, ".env")

    if not os.path.exists(caminho_env):
        return None

    with open(caminho_env, encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if linha.startswith(f"{chave}="):
                return linha.split("=", 1)[1].strip() or None

    return None


def _pasta_backup_extra():
    """Pasta opcional de backup externo (ver INSTALAR.md, secao
    "Backup fora da loja") -- tipicamente uma pasta sincronizada com
    OneDrive/Google Drive/Dropbox, configurada via
    VERTEXERP_BACKUP_EXTRA no .env. O backup local (Documentos)
    continua acontecendo do mesmo jeito de sempre -- essa e so uma
    SEGUNDA copia, opcional, que o app do serviço de nuvem instalado
    no Windows se encarrega de levar pra fora da loja sozinho, sem o
    Vertex precisar falar com nenhuma nuvem diretamente. Devolve None
    se nao configurado."""

    caminho = _ler_env("VERTEXERP_BACKUP_EXTRA")

    if not caminho:
        return None

    os.makedirs(caminho, exist_ok=True)
    return caminho


def _fazer_backup():
    """pg_dump do banco portatil que o proprio launcher gerencia -- os
    caminhos e credenciais (PG_BIN/PG_PORT/PG_SUPERUSER/PG_SUPERSENHA/
    PG_BANCO) ja sao conhecidos com certeza aqui, sem precisar adivinhar
    onde o backend empacotado ficou nem ler nenhum .env."""

    destino = _pasta_backups()

    agora = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    arquivo = os.path.join(destino, f"vertexerp_{agora}.sql")

    ambiente = os.environ.copy()
    ambiente["PGPASSWORD"] = PG_SUPERSENHA

    resultado = subprocess.run(
        [
            os.path.join(PG_BIN, "pg_dump.exe"),
            "-h", "127.0.0.1",
            "-p", PG_PORT,
            "-U", PG_SUPERUSER,
            "-F", "p",
            "-f", arquivo,
            PG_BANCO,
        ],
        capture_output=True,
        text=True,
        env=ambiente,
        creationflags=CREATE_NO_WINDOW,
    )

    if resultado.returncode != 0:
        raise RuntimeError(f"pg_dump falhou:\n{resultado.stderr}")

    pasta_extra = _pasta_backup_extra()

    if pasta_extra:
        try:
            shutil.copy2(arquivo, os.path.join(pasta_extra, os.path.basename(arquivo)))
        except OSError:
            # a copia externa e um extra -- se a pasta sincronizada
            # estiver temporariamente inacessivel (OneDrive pausado,
            # pendrive desconectado etc.), o backup local (que ja deu
            # certo acima) nao pode ser perdido por causa disso
            pass

    return arquivo


def _limpar_backups_antigos():
    limite = datetime.now() - timedelta(days=DIAS_PARA_MANTER_BACKUP)

    pastas = [_pasta_backups()]

    pasta_extra = _pasta_backup_extra()
    if pasta_extra:
        pastas.append(pasta_extra)

    for destino in pastas:
        try:
            nomes = os.listdir(destino)
        except OSError:
            continue

        for nome in nomes:
            if not nome.endswith(".sql"):
                continue

            caminho = os.path.join(destino, nome)

            try:
                modificado = datetime.fromtimestamp(os.path.getmtime(caminho))
                if modificado < limite:
                    os.remove(caminho)
            except OSError:
                continue


def _loop_backup_diario():
    while True:
        try:
            _fazer_backup()
            _limpar_backups_antigos()
        except Exception:
            # backup automatico e complemento, nunca pode derrubar o
            # launcher nem travar a abertura do sistema -- se falhar
            # (disco cheio, pg_dump nao encontrado etc.), so tenta de
            # novo no proximo ciclo.
            pass

        time.sleep(_INTERVALO_BACKUP_SEGUNDOS)


def iniciar_backup_diario():
    """Chamado uma vez, depois que o backend confirma que subiu (ver
    main()) -- dispara o primeiro backup quase na hora, depois repete
    a cada 24h numa thread em segundo plano (daemon: nao impede o
    launcher de fechar normalmente quando o usuario sai do sistema)."""

    threading.Thread(target=_loop_backup_diario, daemon=True).start()


def _mostrar_erro(titulo, mensagem):
    ctypes.windll.user32.MessageBoxW(None, mensagem, titulo, 0x10)


def main():
    if not obter_trava():
        return

    if caminho_tem_caractere_nao_ascii():
        _mostrar_erro(
            "Caminho de instalação inválido",
            "A pasta do Vertex ERP está num caminho com acento ou "
            "caractere especial:\n\n"
            f"{BASE_DIR}\n\n"
            "O banco de dados não consegue iniciar nesse caso. Mova "
            "essa pasta inteira pra um caminho simples, sem acentos "
            "nem espaços incomuns — por exemplo:\n\n"
            "C:\\VertexERP\n\n"
            "Depois, se quiser um atalho na Área de Trabalho, crie um "
            "atalho apontando pro VertexERP.exe de lá (o atalho em si "
            "pode ficar na Área de Trabalho normalmente — só a pasta "
            "de instalação não pode).",
        )

        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)

        return

    try:
        garantir_env()
        inicializar_cluster_se_necessario()
        iniciar_postgres()
        garantir_banco_vertexerp()

        backend = iniciar_backend()

        if backend is None:
            _mostrar_erro(
                "Erro ao iniciar",
                "Não foi possível iniciar o backend do Vertex ERP.\n\n"
                "Tente abrir de novo. Se continuar falhando, verifique "
                "o arquivo pgdata_log.txt na pasta do sistema.",
            )
            return

        iniciar_backup_diario()

        frontend = iniciar_frontend()
        frontend.wait()

        encerrar_processo(FRONTEND_EXE)
        encerrar_processo(BACKEND_EXE)

    except Exception as e:
        # Sem isso, qualquer erro aqui (initdb falhar, pg_ctl falhar,
        # createdb falhar) mata o processo em silêncio — é um app
        # --noconsole, não tem terminal pra mostrar o traceback.
        import traceback

        detalhes = traceback.format_exc()

        try:
            with open(
                os.path.join(BASE_DIR, "erro_launcher.txt"),
                "w",
                encoding="utf-8",
            ) as arquivo:
                arquivo.write(detalhes)
        except OSError:
            pass

        _mostrar_erro(
            "Erro ao iniciar o Vertex ERP",
            f"{e}\n\n"
            "Detalhes salvos em erro_launcher.txt, na pasta do sistema.",
        )

    finally:
        parar_postgres()

        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)


if __name__ == "__main__":
    main()
