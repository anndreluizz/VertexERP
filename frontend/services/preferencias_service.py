"""Preferências locais por usuário — layout do dashboard, atalhos configuráveis.

Guardadas num arquivo .ini em %APPDATA%/VertexERP, sem depender de nenhuma
tabela no banco: cada instalação do Vertex ERP já é independente hoje (ver
INSTALAR.md), então preferência de interface acompanha a mesma lógica —
fica na máquina, não precisa sincronizar com o servidor. Chaveado por
usuario_id pra não embaralhar quando dois caixas usam o mesmo PC.
"""

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
