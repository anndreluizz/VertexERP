"""Preferências locais por usuário — layout do dashboard, atalhos configuráveis.

Guardadas num arquivo .ini em %APPDATA%/VertexERP, sem depender de nenhuma
tabela no banco: cada instalação do Vertex ERP já é independente hoje (ver
INSTALAR.md), então preferência de interface acompanha a mesma lógica —
fica na máquina, não precisa sincronizar com o servidor. Chaveado por
usuario_id pra não embaralhar quando dois caixas usam o mesmo PC.
"""

import base64
import json

from PySide6.QtCore import QSettings


def _settings():
    return QSettings(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        "VertexERP",
        "VertexERP",
    )


def _chave(usuario_id, nome):
    return f"usuarios/{usuario_id}/{nome}"


def salvar(usuario_id, nome, valor):
    _settings().setValue(_chave(usuario_id, nome), json.dumps(valor))


def carregar(usuario_id, nome, padrao=None):
    bruto = _settings().value(_chave(usuario_id, nome))

    if bruto is None:
        return padrao

    try:
        return json.loads(bruto)
    except (TypeError, ValueError):
        return padrao


# ==========================================
# CONFIGURAÇÃO DA MÁQUINA (não é por usuário — precisa existir antes de
# qualquer login, ex.: endereço do servidor num PC-terminal)
# ==========================================

def salvar_servidor(host):
    _settings().setValue("conexao/servidor_host", host)


def carregar_servidor():
    return _settings().value("conexao/servidor_host")


def salvar_loja_id(loja_id):
    """Qual loja este terminal opera -- fixo por instalacao (decisao
    do projeto: quem decide a loja de uma venda/caixa/estoque e o
    terminal, nao o usuario logado nele, ver backend
    app/auth/dependencies.resolver_loja_id). Um PC configurado como
    "Filial" sempre grava como Filial, mesmo se um admin da Matriz
    logar ali."""
    if loja_id is None:
        # remove a chave em vez de gravar None literal -- QSettings
        # guarda tudo como string no .ini, entao um None vira "None"
        # de verdade se so' fizer setValue, e carregar_loja_id() nunca
        # mais devolveria None de volta
        _settings().remove("conexao/loja_id")
    else:
        _settings().setValue("conexao/loja_id", loja_id)


def carregar_loja_id():
    # None (nenhuma configuracao ainda) faz o backend cair no proprio
    # fallback (loja de origem do usuario, ou a loja ativa mais
    # antiga) -- ver resolver_loja_id() no backend
    valor = _settings().value("conexao/loja_id", defaultValue=None)
    return int(valor) if valor is not None else None


def salvar_tema_escuro(escuro):
    _settings().setValue("aparencia/tema_escuro", escuro)


def carregar_tema_escuro():
    # QSettings guarda bool como string ("true"/"false") em .ini --
    # sem o type=bool a leitura de volta pode virar string truthy
    # sempre (mesmo "false" vira True em bool("false")), acendendo o
    # tema escuro sozinho na primeira leitura depois de salvo
    return _settings().value(
        "aparencia/tema_escuro", defaultValue=False, type=bool
    )


def salvar_impressora_termica(configuracao):
    """Configuração da impressora térmica (ESC/POS) -- é da máquina,
    não da loja nem do usuário: cada terminal pode ter uma impressora
    física diferente conectada (ver services/impressora_termica_service.py).
    Guardada como JSON (mesmo padrão de salvar/carregar acima)."""
    _settings().setValue("impressora_termica/configuracao", json.dumps(configuracao))


def carregar_impressora_termica():
    bruto = _settings().value("impressora_termica/configuracao")

    if bruto is None:
        return None

    try:
        return json.loads(bruto)
    except (TypeError, ValueError):
        return None


def _proteger(texto):
    """Criptografa usando o DPAPI do Windows (win32crypt) -- a chave
    fica atrelada à conta do Windows que gravou, então o resultado só
    pode ser lido de volta pelo mesmo usuário do Windows na mesma
    máquina (copiar o .ini pra outro PC/usuário não adianta nada).
    Usado pro refresh_token da sessão lembrada ("Manter conectado"),
    que fica válido por 90 dias -- não faz sentido guardar isso em
    texto puro no .ini como o resto das preferências aqui."""
    import win32crypt

    protegido = win32crypt.CryptProtectData(
        texto.encode("utf-8"), "VertexERP", None, None, None, 0
    )
    return base64.b64encode(protegido).decode("ascii")


def _desproteger(texto_b64):
    import win32crypt

    dados = base64.b64decode(texto_b64)
    _descricao, original = win32crypt.CryptUnprotectData(dados, None, None, None, 0)
    return original.decode("utf-8")


def salvar_sessao(refresh_token):
    """"Manter conectado" marcado no login -- guarda só o refresh_token
    (não o access_token, que expira em minutos e não serve de nada
    guardado; o access_token novo é sempre pedido de novo na abertura
    seguinte, ver services/api.py: retomar_sessao())."""
    _settings().setValue("sessao/refresh_token", _proteger(refresh_token))


def carregar_sessao():
    """Devolve o refresh_token guardado, ou None se não tinha nenhum
    (ou se não deu pra descriptografar -- ex.: arquivo .ini copiado
    de outra máquina/usuário, o que é esperado falhar de propósito)."""

    protegido = _settings().value("sessao/refresh_token")

    if not protegido:
        return None

    try:
        return _desproteger(protegido)
    except Exception:
        return None


def limpar_sessao():
    _settings().remove("sessao/refresh_token")
