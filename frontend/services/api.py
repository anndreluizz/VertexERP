import os
import sys
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter

from services import tls_confianca, preferencias_service

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

# populado por me() (chamado sempre no login/retomada de sessao, ver
# login.py::_buscar_info_principal e PrincipalWindow.__init__) -- deixa
# usuario_tem_permissao()/usuario_e_admin() responderem sem bater na
# rede de novo toda vez que uma tela quiser esconder um botao restrito
_INFO_USUARIO_CACHE = {}


class _AdaptadorSemChecagemDeHostname(HTTPAdapter):
    """O pin do TOFU (ver tls_confianca.py) já garante que o
    certificado é byte-a-byte o mesmo que foi confiado antes -- exigir
    que o hostname/IP bata também é redundante aqui, e quebra na
    prática: o certificado autoassinado só cobre os IPs que a máquina
    tinha na hora de ser gerado (ver backend/app/core/tls.py), o que
    nunca inclui um IP de VPN tipo Tailscale."""

    def cert_verify(self, conn, url, verify, cert):
        super().cert_verify(conn, url, verify, cert)
        conn.assert_hostname = False


_SESSAO = requests.Session()
_SESSAO.mount("https://", _AdaptadorSemChecagemDeHostname())


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


_TIMEOUT_PADRAO = (5, 20)  # (conectar, ler) em segundos


def _requisitar(func, *args, **kwargs):
    """Envolve toda chamada requests.* -- injeta o verify= certo (ver
    _verify_ssl) e traduz uma falha de certificado (pin salvo não bate
    mais) numa mensagem clara em vez do erro críptico padrão do
    requests/urllib3. Em localhost, reconfia sozinho -- não tem rede no
    meio pra desconfiar de verdade (ver tls_confianca.eh_endereco_local).

    kwargs.setdefault("timeout", ...): sem isso, requests espera pra
    sempre (timeout=None é o padrão dele) -- uma conexão que trava no
    meio (rede caiu, servidor pendurado) congelava a janela inteira
    indefinidamente, não só "por uns segundos". 20s de leitura cobre
    uma escrita mais pesada (ex.: venda com muitos itens); quem
    precisa de um teto mais curto (existe_usuario, testar_conexao) já
    passa o próprio timeout= explícito, que kwargs.setdefault respeita."""

    kwargs.setdefault("verify", _verify_ssl())
    kwargs.setdefault("timeout", _TIMEOUT_PADRAO)
    metodo = getattr(_SESSAO, func.__name__)

    try:
        return metodo(*args, **kwargs)
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


def login(usuario: str, senha: str, lembrar: bool = False):
    """Devolve (True, None, None) no sucesso, (False, mensagem, None)
    na falha, ou (False, None, verificacao_id) quando o usuario tem
    2FA ativo -- nesse caso o login ainda nao terminou, quem chamou
    precisa pedir o codigo (mandado por e-mail) e chamar
    verificar_codigo_2fa() com o verificacao_id devolvido aqui (e o
    mesmo "lembrar") pra completar. A mensagem de erro vem do "detail"
    que o backend manda (senha errada, usuario desativado, bloqueio
    por excesso de tentativas etc.), pra quem chamou poder mostrar o
    motivo real em vez de um aviso generico igual pra qualquer causa.

    lembrar=True ("Manter conectado" marcado na tela) guarda o
    refresh_token localmente (protegido por DPAPI, ver
    preferencias_service.salvar_sessao) -- na proxima vez que o app
    abrir, retomar_sessao() usa isso pra pular a tela de login."""

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

        dados = response.json()

        if dados.get("requer_2fa"):
            return False, None, dados["verificacao_id"]

        TOKEN = dados["access_token"]

        if lembrar and dados.get("refresh_token"):
            preferencias_service.salvar_sessao(dados["refresh_token"])

        return True, None, None

    try:
        mensagem = response.json().get("detail") or "Usuário ou senha inválidos."
    except Exception:
        mensagem = "Usuário ou senha inválidos."

    return False, mensagem, None


def verificar_codigo_2fa(verificacao_id: str, codigo: str, lembrar: bool = False):
    """2o passo do login pra quem tem 2FA ativo (ver login() acima) --
    devolve (True, None) no sucesso ou (False, mensagem) se o codigo
    estiver errado/expirado. lembrar tem o mesmo efeito que em
    login()."""

    global TOKEN

    response = _requisitar(
        requests.post,
        f"{URL}/auth/verificar-2fa",
        json={
            "verificacao_id": verificacao_id,
            "codigo": codigo,
        },
    )

    if response.status_code == 200:

        dados = response.json()

        TOKEN = dados["access_token"]

        if lembrar and dados.get("refresh_token"):
            preferencias_service.salvar_sessao(dados["refresh_token"])

        return True, None

    try:
        mensagem = response.json().get("detail") or "Código inválido."
    except Exception:
        mensagem = "Código inválido."

    return False, mensagem


def logout():

    global TOKEN, _INFO_USUARIO_CACHE

    TOKEN = None
    _INFO_USUARIO_CACHE = {}
    preferencias_service.limpar_sessao()


def retomar_sessao():
    """Tenta retomar uma sessao lembrada ("Manter conectado" marcado
    num login anterior) sem pedir senha de novo -- troca o
    refresh_token guardado localmente por um access_token novo (ver
    /auth/refresh no backend). Devolve True se conseguiu (TOKEN ja
    fica setado), False se nao tinha sessao guardada ou ela nao vale
    mais (expirou depois de 90 dias, foi revogada em Sessoes, ou o
    servidor mudou) -- nesse caso quem chamou deve mostrar a tela de
    login normal."""

    global TOKEN

    refresh_token = preferencias_service.carregar_sessao()

    if not refresh_token:
        return False

    try:
        response = _requisitar(
            requests.post,
            f"{URL}/auth/refresh",
            json={"refresh_token": refresh_token},
        )
    except Exception:
        return False

    if response.status_code != 200:
        preferencias_service.limpar_sessao()
        return False

    TOKEN = response.json()["access_token"]

    return True


def servidor_online():
    """Checagem leve de conectividade (rota / , sem autenticacao) --
    usada pelo indicador de "sem conexao" do Header (ver
    PrincipalWindow), rodando em segundo plano a cada alguns segundos.
    Nunca levanta excecao: qualquer falha (rede, timeout, certificado)
    so' significa "offline" pra quem esta perguntando."""

    try:
        response = _requisitar(requests.get, f"{URL}/", timeout=3)
        return response.status_code == 200
    except Exception:
        return False


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


def endpoint_com_loja(endpoint: str) -> str:
    """Anexa ?loja_id=X (ou &loja_id=X se o endpoint ja tiver
    querystring) usando a loja fixa configurada pra este terminal --
    usado nos endpoints que precisam saber em qual loja registrar uma
    escrita (venda, caixa, estoque, contas a pagar, cadastro/edicao de
    produto) ou filtrar uma leitura pelo estoque fisico dessa loja
    (listagem/busca de produto, PDV). Sem configuracao nenhuma
    (carregar_loja_id() == None), devolve o endpoint como veio e o
    backend cai no proprio fallback (ver
    app/auth/dependencies.resolver_loja_id)."""

    loja_id = preferencias_service.carregar_loja_id()

    if loja_id is None:
        return endpoint

    separador = "&" if "?" in endpoint else "?"
    return f"{endpoint}{separador}loja_id={loja_id}"


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

    response = get(endpoint_com_loja("/dashboard"))

    if response.status_code == 200:
        return response.json()

    return {}


def me():

    global _INFO_USUARIO_CACHE

    response = get("/auth/me")

    if response.status_code == 200:
        _INFO_USUARIO_CACHE = response.json()
        return _INFO_USUARIO_CACHE

    return {}


def usuario_e_admin():
    """Se o usuário logado é administrador -- usado pra esconder ações
    restritas (cancelar venda, gerenciar usuários etc.) de quem não
    tem permissão, além da checagem que o backend já faz. Le do cache
    (ver _INFO_USUARIO_CACHE) em vez de bater na rede de novo -- me()
    ja' roda sempre no login/retomada de sessao."""

    return bool(_INFO_USUARIO_CACHE.get("admin"))


def usuario_tem_permissao(chave: str) -> bool:
    """Se o usuario logado pode fazer 'chave' (ver
    app/auth/permissoes.py no backend pro catalogo) -- admin sempre
    True. So' pra esconder/desabilitar botao na hora certa; o backend
    continua sendo quem de fato barra (ver exigir_permissao)."""

    if _INFO_USUARIO_CACHE.get("admin"):
        return True

    return chave in (_INFO_USUARIO_CACHE.get("permissoes") or [])


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