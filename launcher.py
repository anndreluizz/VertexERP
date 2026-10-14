import ctypes
import ctypes.wintypes
import filecmp
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta

import atualizador

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
# Senha LEGADA: so' vale pra instalacoes criadas antes da senha
# aleatoria por instalacao (ver garantir_env). A senha de verdade vem
# sempre do .env -- ver _senha_banco().
PG_SUPERSENHA = "Vertex2026"
PG_BANCO = "vertexerp"

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


def processo_com_imagem_rodando(caminho_exe):
    """Confere se algum processo com esse nome de imagem está rodando
    (ex.: VertexERP-Frontend.exe) -- usado pra saber se o usuario fechou
    so a janela do frontend (backend/launcher continuam de pe em modo
    Servidor) sem precisar rastrear PID nenhum."""

    nome_imagem = os.path.basename(caminho_exe)

    resultado = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {nome_imagem}"],
        capture_output=True,
        text=True,
    )

    return nome_imagem.lower() in resultado.stdout.lower()


_ERROR_ALREADY_EXISTS = 183

# Guardado em variavel global de proposito: o mutex vive enquanto o
# handle estiver aberto, e o Windows fecha sozinho quando o processo
# morre (crash, Gerenciador de Tarefas, desligar o PC).
_handle_mutex = None


def obter_trava():
    """Garante que só uma instância do sistema fique aberta por vez —
    se o usuário clicar duas vezes no ícone, a segunda simplesmente não
    abre outro backend/PDV por cima do primeiro.

    Mutex nomeado do Windows, nao mais arquivo com PID: no modo
    Servidor o launcher so' termina quando o PC desliga, entao o
    arquivo nunca era apagado -- e depois do reboot, se o PID antigo
    tivesse sido reaproveitado por outro processo, o launcher achava
    que ja estava rodando e nao subia banco nem backend (loja parada
    sem mensagem nenhuma). O mutex nunca fica orfao."""

    global _handle_mutex

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.wintypes.HANDLE

    # nome inclui a pasta: duas instalacoes diferentes no mesmo PC (ex.:
    # teste e producao) nao se bloqueiam
    nome = "Local\\VertexERP_" + BASE_DIR.replace("\\", "_").replace(":", "")

    _handle_mutex = kernel32.CreateMutexW(None, False, nome)

    return ctypes.get_last_error() != _ERROR_ALREADY_EXISTS


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


def _senha_banco():
    return _ler_env("DB_PASSWORD") or PG_SUPERSENHA


def _banco_ja_inicializado():
    # initdb cria esse arquivo como marca de "cluster já criado".
    return os.path.exists(os.path.join(PG_DATA, "PG_VERSION"))


class InicializacaoCancelada(Exception):
    pass


def _existem_backups():
    try:
        return any(n.endswith(".sql") for n in os.listdir(_pasta_backups()))
    except OSError:
        return False


def inicializar_cluster_se_necessario():
    if _banco_ja_inicializado():
        return

    # Sem pgdata MAS com backups neste PC: quase sempre e' pasta movida/
    # copiada sem o pgdata, ou atualizacao extraida no lugar errado --
    # criar um banco vazio calado fazia a loja voltar a vender num banco
    # zerado sem ninguem perceber.
    if _existem_backups() and not _perguntar_sim_nao(
        "Banco de dados não encontrado",
        "Não encontrei o banco de dados do Vertex ERP nesta pasta:\n\n"
        f"{PG_DATA}\n\n"
        "Mas existem backups deste sistema neste computador. Se você "
        "moveu ou copiou a pasta do Vertex, feche e abra pela pasta "
        "certa (a que tem o pgdata).\n\n"
        "Criar um banco NOVO e VAZIO aqui?\n\n"
        "(Para recuperar os dados num banco novo: escolha Sim, feche o "
        "sistema depois que abrir e rode restaurar_backup.ps1.)",
    ):
        raise InicializacaoCancelada()

    os.makedirs(PG_DATA, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False
    ) as arquivo_senha:
        arquivo_senha.write(_senha_banco())
        caminho_senha = arquivo_senha.name

    try:
        subprocess.run(
            [
                os.path.join(PG_BIN, "initdb.exe"),
                "-D", PG_DATA,
                "-U", PG_SUPERUSER,
                "--pwfile", caminho_senha,
                # sem -A o initdb usa "trust": qualquer processo deste PC
                # entrava como superusuario SEM senha. So' vale pra
                # cluster novo -- os que ja existem nao sao mexidos.
                "-A", "scram-sha-256",
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
    env["PGPASSWORD"] = _senha_banco()

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


def _perguntar_na_frente(titulo, mensagem):
    """Igual _perguntar_sim_nao, mas por cima da janela do Vertex aberta
    (MB_SYSTEMMODAL | MB_SETFOREGROUND) -- usada pela atualizacao, que
    pergunta com o sistema ja em uso."""
    resposta = ctypes.windll.user32.MessageBoxW(
        None, mensagem, titulo, 0x4 | 0x20 | 0x1000 | 0x10000
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

    # Senha do banco: aleatoria por instalacao quando o cluster ainda vai
    # ser criado agora (instalacao nova -- initdb usa essa senha, ver
    # inicializar_cluster_se_necessario). Cluster que ja existe (so' o
    # .env sumiu) continua com a senha antiga, senao ninguem conecta.
    senha_banco = (
        PG_SUPERSENHA if _banco_ja_inicializado() else secrets.token_urlsafe(24)
    )

    with open(caminho_env, "w", encoding="utf-8") as arquivo:
        arquivo.write(
            "APP_NAME=Vertex ERP\n"
            "APP_VERSION=1.0.0\n\n"
            "DB_HOST=127.0.0.1\n"
            f"DB_PORT={PG_PORT}\n"
            f"DB_NAME={PG_BANCO}\n"
            f"DB_USER={PG_SUPERUSER}\n"
            f"DB_PASSWORD={senha_banco}\n\n"
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

        # processo ja morreu (ex.: exit code 3, migracao falhou) --
        # esperar os 15 minutos inteiros so' atrasava o aviso de erro
        if processo.poll() is not None:
            break

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

# Nos ultimos DIAS_COM_TODOS_OS_BACKUPS fica tudo; dali ate
# DIAS_PARA_MANTER_BACKUP fica so' o ultimo backup de cada dia -- sem
# isso, rodando de hora em hora, a pasta (e a copia no OneDrive, que tem
# cota) cresceria muito mais rapido do que com o backup diario de antes.
DIAS_COM_TODOS_OS_BACKUPS = 7

# 1h: se o PC-Servidor morrer, perde no maximo 1 hora de movimento (era
# 24h, depois 4h -- issue #4: a matriz perdeu dados em 25/09). Backup
# igual ao anterior (noite, loja fechada) e' descartado, entao a pasta
# so cresce quando o banco muda de verdade.
_INTERVALO_BACKUP_SEGUNDOS = 60 * 60

# Lido pelo backend (app/services/backup_service.py) pra avisar o admin
# na tela quando o backup falha -- antes a falha morria calada dentro
# da thread daemon e ninguem ficava sabendo.
_ARQUIVO_STATUS_BACKUP = "status_backup.json"


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
    caminhos e credenciais (PG_BIN/PG_PORT/PG_SUPERUSER/_senha_banco()/
    PG_BANCO) ja sao conhecidos com certeza aqui, sem precisar adivinhar
    onde o backend empacotado ficou nem ler nenhum .env."""

    destino = _pasta_backups()

    agora = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    arquivo = os.path.join(destino, f"vertexerp_{agora}.sql")

    # Grava num .tmp e so' renomeia pra .sql depois de validar: um dump
    # que falha no meio (disco cheio, conexao caiu) deixava um .sql
    # truncado com cara de backup bom -- e a retencao podia manter
    # justamente ele como "o ultimo do dia" e apagar os completos.
    temporario = arquivo + ".tmp"

    ambiente = os.environ.copy()
    ambiente["PGPASSWORD"] = _senha_banco()

    try:
        resultado = subprocess.run(
            [
                os.path.join(PG_BIN, "pg_dump.exe"),
                "-h", "127.0.0.1",
                "-p", PG_PORT,
                "-U", PG_SUPERUSER,
                "-F", "p",
                "-f", temporario,
                PG_BANCO,
            ],
            capture_output=True,
            text=True,
            env=ambiente,
            creationflags=CREATE_NO_WINDOW,
        )

        if resultado.returncode != 0:
            raise RuntimeError(f"pg_dump falhou:\n{resultado.stderr}")

        _validar_dump(temporario)

        ultimo = _backup_mais_recente(destino)
        if ultimo and filecmp.cmp(temporario, ultimo, shallow=False):
            # nada mudou desde o ultimo backup -- ele continua valendo
            return _ler_env("VERTEXERP_BACKUP_EXTRA"), None

        os.replace(temporario, arquivo)

    finally:
        if os.path.exists(temporario):
            os.remove(temporario)

    erro_copia_externa = None
    pasta_extra = None

    try:
        # dentro do try: pasta do OneDrive inacessivel nao pode marcar
        # como "falhou" um backup local que deu certo
        pasta_extra = _pasta_backup_extra()

        if pasta_extra:
            shutil.copy2(arquivo, os.path.join(pasta_extra, os.path.basename(arquivo)))
    except OSError as erro:
        # a copia externa e um extra -- se a pasta sincronizada
        # estiver temporariamente inacessivel (OneDrive pausado,
        # pendrive desconectado etc.), o backup local (que ja deu
        # certo acima) nao pode ser perdido por causa disso. Mas
        # a falha vai pro status, pro admin ficar sabendo.
        erro_copia_externa = str(erro)
        pasta_extra = pasta_extra or _ler_env("VERTEXERP_BACKUP_EXTRA")

    return pasta_extra, erro_copia_externa


def _backup_mais_recente(pasta):
    """Caminho do .sql mais novo da pasta (None se nao tiver)."""
    arquivos = [
        os.path.join(pasta, nome)
        for nome in os.listdir(pasta)
        if nome.endswith(".sql")
    ]
    return max(arquivos, key=os.path.getmtime, default=None)


# Ultima linha que o pg_dump (formato plain) escreve -- se nao estiver
# no fim do arquivo, o dump foi cortado no meio.
_RODAPE_DUMP = b"PostgreSQL database dump complete"


def _validar_dump(caminho):
    tamanho = os.path.getsize(caminho)

    if tamanho == 0:
        raise RuntimeError("pg_dump gerou um arquivo vazio.")

    with open(caminho, "rb") as arquivo:
        arquivo.seek(max(0, tamanho - 4096))
        final = arquivo.read()

    if _RODAPE_DUMP not in final:
        raise RuntimeError(
            "O arquivo de backup ficou incompleto (sem o rodape do "
            "pg_dump) e foi descartado."
        )


# Piso da retencao: os N backups mais recentes nunca sao apagados, seja
# qual for a idade -- se o relogio do PC pular pra frente (bateria da
# BIOS, NTP errado) a regra por idade sozinha apagaria tudo de uma vez.
MINIMO_BACKUPS_MANTIDOS = 10


def _backups_para_apagar(arquivos, agora):
    """Recebe [(caminho, modificado_em)] e devolve os caminhos que a
    politica de retencao manda apagar: tudo com mais de
    DIAS_PARA_MANTER_BACKUP dias, e, entre DIAS_COM_TODOS_OS_BACKUPS e
    esse limite, tudo menos o backup mais recente de cada dia. Os
    MINIMO_BACKUPS_MANTIDOS mais recentes nunca entram na lista."""

    limite_total = agora - timedelta(days=DIAS_PARA_MANTER_BACKUP)
    limite_todos = agora - timedelta(days=DIAS_COM_TODOS_OS_BACKUPS)

    apagar = []
    ultimo_do_dia = {}

    arquivos = sorted(arquivos, key=lambda item: item[1], reverse=True)
    arquivos = arquivos[MINIMO_BACKUPS_MANTIDOS:]

    for caminho, modificado in arquivos:
        if modificado < limite_total:
            apagar.append(caminho)
        elif modificado < limite_todos:
            dia = modificado.date()
            atual = ultimo_do_dia.get(dia)

            if atual is None:
                ultimo_do_dia[dia] = (caminho, modificado)
            elif modificado > atual[1]:
                apagar.append(atual[0])
                ultimo_do_dia[dia] = (caminho, modificado)
            else:
                apagar.append(caminho)

    return apagar


def _limpar_backups_antigos():
    pastas = [_pasta_backups()]

    try:
        pasta_extra = _pasta_backup_extra()
    except OSError:
        pasta_extra = None

    if pasta_extra:
        pastas.append(pasta_extra)

    for destino in pastas:
        try:
            nomes = os.listdir(destino)
        except OSError:
            continue

        arquivos = []

        for nome in nomes:
            caminho = os.path.join(destino, nome)

            # .tmp de um dump interrompido (processo morto no meio) --
            # com mais de 1 dia com certeza nao esta mais sendo escrito
            if nome.endswith(".sql.tmp"):
                try:
                    if time.time() - os.path.getmtime(caminho) > 24 * 3600:
                        os.remove(caminho)
                except OSError:
                    pass
                continue

            if not nome.endswith(".sql"):
                continue

            try:
                arquivos.append(
                    (caminho, datetime.fromtimestamp(os.path.getmtime(caminho)))
                )
            except OSError:
                continue

        for caminho in _backups_para_apagar(arquivos, datetime.now()):
            try:
                os.remove(caminho)
            except OSError:
                continue


def _gravar_status_backup(status):
    try:
        caminho = os.path.join(_pasta_backups(), _ARQUIVO_STATUS_BACKUP)
        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump(status, arquivo, ensure_ascii=False)
    except OSError:
        pass


def _rodar_backup_e_registrar():
    status = {
        "tentativa_em": datetime.now().isoformat(timespec="seconds"),
        "erro": None,
        "copia_externa": None,
        "erro_copia_externa": None,
    }

    try:
        pasta_extra, erro_copia_externa = _fazer_backup()
        status["copia_externa"] = pasta_extra
        status["erro_copia_externa"] = erro_copia_externa
        _limpar_backups_antigos()
    except Exception as erro:
        # backup automatico e complemento, nunca pode derrubar o
        # launcher nem travar a abertura do sistema -- se falhar
        # (disco cheio, pg_dump nao encontrado etc.), registra no
        # status (o admin ve o aviso na tela e recebe push) e tenta de
        # novo no proximo ciclo.
        status["erro"] = str(erro)[:500]

    _gravar_status_backup(status)


def _loop_backup_diario():
    # o primeiro backup ja rodou em main(), antes do backend subir
    while True:
        time.sleep(_INTERVALO_BACKUP_SEGUNDOS)
        _rodar_backup_e_registrar()


def iniciar_backup_diario():
    """Chamado uma vez, depois que o backend confirma que subiu (ver
    main()) -- repete o backup de hora em hora numa thread em segundo plano
    (daemon: nao impede o launcher de fechar normalmente quando o
    usuario sai do sistema). O primeiro backup da sessao roda antes,
    em main(), de forma sincrona."""

    threading.Thread(target=_loop_backup_diario, daemon=True).start()


# ==========================================
# WATCHDOG DO BACKEND -- reinicia sozinho se o processo cair no meio
# da sessao (ex.: um crash por falta de memoria, ver boleto/anexo sem
# limite de tamanho corrigido em cadastro_despesa.py). Sem isso, o
# unico jeito de voltar ao ar era o usuario perceber que parou de
# funcionar e fechar/reabrir o Vertex inteiro na mao -- pior ainda no
# modo Servidor, onde ninguem necessariamente esta olhando pra tela
# desse PC quando o backend cai.
# ==========================================

_INTERVALO_WATCHDOG_SEGUNDOS = 30


def _loop_watchdog_backend(processo_inicial):
    processo = processo_inicial

    while True:
        time.sleep(_INTERVALO_WATCHDOG_SEGUNDOS)

        # so' age quando o PROCESSO de verdade morreu (poll() != None
        # -- sinal inequivoco) -- nao usa backend_pronto() aqui pra nao
        # confundir "backend momentaneamente lento" com "caiu" e subir
        # um segundo processo duplicado brigando pela mesma porta.
        if processo.poll() is None:
            continue

        novo_processo = iniciar_backend()

        if novo_processo is not None:
            processo = novo_processo


def iniciar_watchdog_backend(processo):
    threading.Thread(
        target=_loop_watchdog_backend, args=(processo,), daemon=True
    ).start()


def _mostrar_erro(titulo, mensagem):
    ctypes.windll.user32.MessageBoxW(None, mensagem, titulo, 0x10)


def main():
    if not obter_trava():
        # Ja tem uma instancia rodando (backend/launcher de pe) -- so'
        # significa que o usuario fechou a JANELA do sistema sem
        # encerrar o Vertex inteiro (comum no modo Servidor, onde
        # fechar o frontend nao derruba o backend -- ver finally() mais
        # abaixo). Sem isso, clicar de novo no atalho nao fazia nada:
        # o clique era silenciosamente descartado pela trava de
        # instancia unica, e o unico jeito de reabrir a janela era
        # saber que precisava abrir o VertexERP-Frontend.exe direto, de
        # dentro da pasta.
        if not processo_com_imagem_rodando(FRONTEND_EXE):
            subprocess.Popen(
                [FRONTEND_EXE],
                cwd=BASE_DIR,
                env=ambiente_para_subprocessos(),
            )
        return

    # Se esse PC foi configurado como "Servidor" (ver garantir_env()),
    # outros caixas da loja dependem do backend dele pra funcionar --
    # fechar a janela do Vertex aqui nao pode derrubar backend/Postgres
    # junto, senao a loja inteira para porque alguem fechou o app no
    # PC errado. So sabemos com certeza depois de garantir_env() rodar
    # (ela cria o .env na primeira execucao), entao comeca assumindo
    # que NAO e servidor e corrige antes de decidir o que encerrar.
    modo_servidor = False

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

        return

    try:
        garantir_env()
        modo_servidor = _ler_env("VERTEXERP_HOST") == "0.0.0.0"
        inicializar_cluster_se_necessario()
        iniciar_postgres()
        garantir_banco_vertexerp()

        # Backup ANTES do backend subir: o backend roda `alembic upgrade
        # head` no startup, e uma migracao com bug numa atualizacao
        # nova pode estragar dados -- sem isso o backup mais recente
        # podia ter ate 4h. Se falhar, segue abrindo (registrado no
        # status, o admin e' avisado) -- um PC-Servidor ligando sozinho
        # de madrugada nao pode ficar parado numa pergunta na tela.
        _rodar_backup_e_registrar()

        backend = iniciar_backend()

        if backend is None:
            _mostrar_erro(
                "Erro ao iniciar",
                "Não foi possível iniciar o backend do Vertex ERP.\n\n"
                "Tente abrir de novo. Se continuar falhando, o motivo "
                "está no fim do arquivo "
                "VertexERP-Backend\\backend_log.txt (e, se for o banco "
                "de dados, em pgdata_log.txt), na pasta do sistema.",
            )
            return

        iniciar_backup_diario()
        iniciar_watchdog_backend(backend)

        # atualizacao automatica pelo GitHub (ver atualizador.py);
        # VERTEXERP_ATUALIZAR=0 no .env desliga
        if _ler_env("VERTEXERP_ATUALIZAR") != "0":
            atualizador.iniciar_verificacao(BASE_DIR, _perguntar_na_frente, _mostrar_erro)

        frontend = iniciar_frontend()
        frontend.wait()

        encerrar_processo(FRONTEND_EXE)

        if not modo_servidor:
            encerrar_processo(BACKEND_EXE)
        else:
            # Backend/Postgres continuam de pe pros outros caixas da
            # loja -- o launcher tambem precisa continuar vivo (nao
            # sair de main()), senao a thread do backup diario
            # (daemon: some junto com o processo que a criou) para de
            # rodar mesmo com o backend ainda de pe. So termina esse
            # loop matando o processo do launcher (Gerenciador de
            # Tarefas) ou desligando o PC.
            while True:
                time.sleep(3600)

    except InicializacaoCancelada:
        # usuario escolheu nao criar banco vazio -- so' sai
        return

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
        if not modo_servidor:
            parar_postgres()


if __name__ == "__main__":
    main()
