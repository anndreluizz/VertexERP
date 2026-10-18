from pydantic import EmailStr

from app.schemas.base import Schema


class UserCreate(Schema):
    nome: str
    email: EmailStr
    senha: str


class UserLogin(Schema):
    email: EmailStr
    senha: str
    # opcional -- so o app mobile envia (ex.: "Android - Pixel 7"), pra
    # aparecer identificavel na tela de Sessoes. Desktop nao manda nada
    # e continua funcionando igual (fica None).
    dispositivo: str | None = None


class UserUpdate(Schema):
    nome: str | None = None
    ativo: bool | None = None
    admin: bool | None = None
    dois_fatores_ativo: bool | None = None
    perfil_id: int | None = None


class UserAdminUpdate(Schema):
    admin: bool


class UserAtivoUpdate(Schema):
    ativo: bool


class Verificar2FARequest(Schema):
    """Segundo passo do login quando o usuario tem 2FA ativo (ver
    POST /auth/verificar-2fa) -- verificacao_id e o que voltou do
    primeiro passo (POST /auth/login), codigo e o numero de 6 digitos
    que chegou por e-mail."""
    verificacao_id: str
    codigo: str
    dispositivo: str | None = None


class TrocarSenhaRequest(Schema):
    """Usuário trocando a própria senha -- precisa confirmar a senha
    atual (ver /auth/senha)."""
    senha_atual: str
    senha_nova: str


class RedefinirSenhaRequest(Schema):
    """Admin redefinindo a senha de outro usuário (ex.: funcionário
    esqueceu a senha) -- não precisa da senha atual (ver
    /users/{user_id}/senha)."""
    senha_nova: str


class UserResponse(Schema):
    id: int
    nome: str
    email: EmailStr
    ativo: bool
    admin: bool
    dois_fatores_ativo: bool = False
    # None pra admin sem loja de origem fixa (ver resolver_loja_id) --
    # o app mobile usa isso pra saber de qual loja mostrar os dados,
    # já que (ao contrário do Desktop) não tem terminal fixo por loja.
    loja_id: int | None = None
    perfil_id: int | None = None
    perfil_nome: str | None = None
    permissoes: list[str] = []
