import os
import sys
from urllib.parse import urlparse

import requests

from services import tls_confianca

# Esse mesmo arquivo roda em dois contextos com portas padrao diferentes:
# o frontend de dev puro (python app.py, sys.frozen=False) fala com
# "uvicorn main:app" rodando na 8000 (padrao do proprio uvicorn); ja o
# frontend empacotado (VertexERP-Frontend.exe, sys.frozen=True) fala com
# o backend empacotado, que usa 58734 de proposito pra nunca colidir com
# um backend de dev na mesma maquina (ver backend/backend_entry.py).
# VERTEXERP_PORT sempre pode sobrescrever os dois, pra testes isolados.
_PORTA_PADRAO = "58734" if getattr(sys, "frozen", False) else "8000"
URL = f"https://127.0.0.1:{os.getenv('VERTEXERP_PORT', _PORTA_PADRAO)}"

TOKEN = None


class CertificadoServidorMudou(Exception):
    """O servidor apresentou um certificado diferente do que estava
    salvo como confiável (ver services/tls_confianca.py) -- mensagem já
    pronta pra aparecer direto nos vários "except Exception as e:
    ...str(e)..." espalhados pelas telas, sem precisar tratar esse
    caso em cada uma."""

    def __init__(self):
        super().__init__(
            "O servidor mudou de identidade (o certificado é diferente "
            "do que estava salvo). Isso é esperado se o Servidor foi "
            "reinstalado recentemente -- nesse caso, abra 'Configurar "
            "servidor' e teste a conexão de novo pra confiar no "
            "certificado atual. Se você não fez nenhuma mudança "
            "recente, pode ser um problema de segurança na rede."
        )


def definir_url(endereco):
    """Aponta pra um backend em outra máquina (modo Terminal) — chamado
    uma vez no início do app.py, a partir do endereço salvo em
    preferencias_service. Sem isso, URL continua o padrão localhost de
    sempre (instalação de um PC só, sem mudança nenhuma de comportamento)."""

    global URL

    endereco = (endereco or "").strip()

    if not endereco:
        return

    if not endereco.startswith("http://") and not endereco.startswith("https://"):
        endereco = f"https://{endereco}"

    resto = endereco.split("://", 1)[1]

    if ":" not in resto:
        endereco = f"{endereco}:{_PORTA_PADRAO}"

    URL = endereco


def _verify_ssl():
    """Devolve o valor certo pro verify= do requests pra falar com a
    URL atual -- confia automaticamente (TOFU, mesmo modelo do SSH) no
    primeiro contato com um servidor, e a partir daí passa a EXIGIR
    esse mesmo certificado em toda chamada seguinte."""

    partes = urlparse(URL)
    host = partes.hostname
    porta = partes.port or 443

    if not host:
        return True

    if not tls_confianca.esta_confiavel(host, porta):
        try:
            tls_confianca.confiar(host, porta)
        except Exception:
            # nao conseguiu nem buscar o certificado (servidor fora do
            # ar, endereco errado etc.) -- deixa a requisicao de
            # verdade abaixo falhar do jeito normal, com a mensagem de
            # conexao que ja existe pra esse caso
            return True

    return tls_confianca.caminho_pinado(host, porta)


def _requisitar(func, *args, **kwargs):
    """Envolve toda chamada requests.* -- injeta o verify= certo (ver
    _verify_ssl) e traduz uma falha de certificado (pin salvo não bate
    mais) numa mensagem clara em vez do erro críptico padrão do
    requests/urllib3. Em localhost, reconfia sozinho -- não tem rede no
    meio pra desconfiar de verdade (ver tls_confianca.eh_endereco_local)."""

    kwargs.setdefault("verify", _verify_ssl())

    try:
        return func(*args, **kwargs)
    except requests.exceptions.SSLError:

        partes = urlparse(URL)
        host = partes.hostname
        porta = partes.port or 443

        if tls_confianca.eh_endereco_local(host):
            tls_confianca.confiar(host, porta)
            kwargs["verify"] = tls_confianca.caminho_pinado(host, porta)
            return func(*args, **kwargs)

        raise CertificadoServidorMudou()


def testar_conexao(endereco):
    """Usado pela tela de Configurar Servidor -- aponta a URL global
    pro endereço informado e tenta uma conexão de teste, com o mesmo
    tratamento de certificado (TOFU) de qualquer outra chamada. Deixa
    CertificadoServidorMudou passar pra quem chamou decidir (a tela
    tem um fluxo próprio de "confiar de novo?" pra esse caso)."""

    definir_url(endereco)
    return _requisitar(requests.get, f"{URL}/", timeout=3)


def confiar_de_novo_no_servidor_atual():
    """Depois que o usuário confirma "sim, confio nesse certificado
    novo" (ver telas/conectar_servidor.py) -- sobrescreve o pin salvo
    com o certificado que o servidor está apresentando agora."""

    partes = urlparse(URL)
    tls_confianca.confiar(partes.hostname, partes.port or 443)


def login(usuario: str, senha: str):
    """Devolve (True, None) no sucesso, ou (False, mensagem) na falha
    -- a mensagem vem do "detail" que o backend manda (senha errada,
    usuário desativado, bloqueio por excesso de tentativas etc.), pra
    quem chamou poder mostrar o motivo real em vez de um aviso
    genérico igual pra qualquer causa."""

    global TOKEN

    response = _requisitar(
        requests.post,
        f"{URL}/auth/login",
        json={
            "email": usuario,
            "senha": senha,
        },
    )

    if response.status_code == 200:

        TOKEN = response.json()["access_token"]

        return True, None

    try:
        mensagem = response.json().get("detail") or "Usuário ou senha inválidos."
    except Exception:
        mensagem = "Usuário ou senha inválidos."

    return False, mensagem


def logout():

    global TOKEN

    TOKEN = None


def existe_usuario():

    # timeout curto de proposito -- essa chamada roda no arranque do
    # app (ver app.py), antes de qualquer tela aparecer. Sem timeout,
    # um PC Terminal apontando pra um servidor que nao responde (fora
    # do ar, endereco errado, rede lenta) trava o app inteiro sem
    # feedback nenhum em vez de cair no dialogo de reconfigurar o
    # endereco que ja existe pra esse caso.
    response = _requisitar(requests.get, f"{URL}/users/existe", timeout=5)

    if response.status_code != 200:
        # se o backend nao respondeu direito, assume que ja existe
        # usuario pra nao empurrar quem ja usa o sistema de volta
        # pro cadastro inicial
        return True

    return response.json().get("data", {}).get("existe", True)


def cadastrar_usuario(nome, email, senha):

    return _requisitar(
        requests.post,
        f"{URL}/users/",
        json={
            "nome": nome,
            "email": email,
            "senha": senha,
        },
    )


def get(endpoint: str):

    if TOKEN is None:
        raise Exception("Usuário não autenticado.")

    return _requisitar(
        requests.get,
        URL + endpoint,
        headers={
            "Authorization": f"Bearer {TOKEN}"
        },
    )


def post(endpoint: str, dados: dict):

    if TOKEN is None:
        raise Exception("Usuário não autenticado.")

    return _requisitar(
        requests.post,
        URL + endpoint,
        json=dados,
        headers={
            "Authorization": f"Bearer {TOKEN}"
        },
    )


def put(endpoint: str, dados: dict):

    if TOKEN is None:
        raise Exception("Usuário não autenticado.")

    return _requisitar(
        requests.put,
        URL + endpoint,
        json=dados,
        headers={
            "Authorization": f"Bearer {TOKEN}"
        },
    )


def delete(endpoint: str):

    if TOKEN is None:
        raise Exception("Usuário não autenticado.")

    return _requisitar(
        requests.delete,
        URL + endpoint,
        headers={
            "Authorization": f"Bearer {TOKEN}"
        },
    )


def dashboard():

    response = get("/dashboard")

    if response.status_code == 200:
        return response.json()

    return {}


def me():

    response = get("/auth/me")

    if response.status_code == 200:
        return response.json()

    return {}


def usuario_e_admin():
    """Se o usuário logado é administrador -- usado pra esconder ações
    restritas (cancelar venda, gerenciar usuários etc.) de quem não
    tem permissão, além da checagem que o backend já faz."""

    return bool(me().get("admin"))


def configuracoes():

    response = get("/configuracoes")

    if response.status_code == 200:
        return response.json()

    return {}


def atualizar_configuracoes(dados):

    return put("/configuracoes/", dados)


def trocar_senha(senha_atual, senha_nova):

    return put(
        "/auth/senha",
        {
            "senha_atual": senha_atual,
            "senha_nova": senha_nova,
        },
    )