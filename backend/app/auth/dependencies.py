from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.auth.jwt import SECRET_KEY, ALGORITHM
from app.database.session import SessionLocal
from app.models.loja import Loja
from app.models.perfil import Perfil
from app.models.user import User
from app.services.log_auditoria_service import LogAuditoriaService

security = HTTPBearer()
security_opcional = HTTPBearer(auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get("id")

        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail="Token inválido."
            )

        usuario = (
            db.query(User)
            .filter(User.id == user_id)
            .first()
        )

        if usuario is None:
            raise HTTPException(
                status_code=401,
                detail="Usuário não encontrado."
            )

        if not usuario.ativo:
            raise HTTPException(
                status_code=403,
                detail="Usuário desativado.",
            )

        return usuario

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Token inválido."
        )


def resolver_loja_id(db: Session, usuario: User, loja_id_informado: int | None = None):
    """Decide em qual loja uma escrita (venda, abertura de caixa, ajuste
    de estoque, conta a pagar/receber) deve ser registrada.

    Prioridade: (1) loja_id que o TERMINAL mandou explicitamente na
    requisicao -- e o terminal, nao o usuario, que sabe em qual loja
    fisica ele esta instalado (ver frontend, config local por PC); (2)
    a loja de origem do usuario logado; (3) admin sem loja de origem
    (enxerga todas) e sem terminal configurado ainda cai na loja ativa
    mais antiga, pra nao travar o sistema enquanto o terminal nao manda
    esse dado (frontend ainda nao implementa isso)."""

    if loja_id_informado is not None:
        return loja_id_informado

    if usuario.loja_id is not None:
        return usuario.loja_id

    loja = (
        db.query(Loja)
        .filter(Loja.ativa.is_(True))
        .order_by(Loja.id)
        .first()
    )

    return loja.id if loja else None


def _ip_do_pedido(request: Request | None) -> str | None:
    return request.client.host if request and request.client else None


def get_current_admin(
    request: Request,
    usuario: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not usuario.admin:
        raise HTTPException(
            status_code=403,
            detail="Apenas administradores podem realizar essa ação.",
        )

    # sem uma chave de permissao pra usar como rotulo (get_current_admin
    # e' usado em rotas que ficam admin-only pra sempre, ver
    # app/auth/permissoes.py), o metodo+caminho da requisicao ja' da'
    # WHO/WHEN/WHERE/O-QUE suficiente pra auditoria
    LogAuditoriaService.registrar(
        db, usuario.id,
        f"{request.method} {request.url.path}",
        ip=_ip_do_pedido(request),
    )

    return usuario


def exigir_permissao(chave: str):
    """Dependency factory -- Depends(exigir_permissao("produtos.excluir"))
    numa rota. Admin sempre passa (superusuario); usuario comum passa
    so' se o Perfil dele tiver essa chave (ver app/models/perfil.py e
    app/auth/permissoes.py pro catalogo valido). Toda autorizacao
    concedida (admin ou via perfil) vira uma linha em LogAuditoria."""

    def dependencia(
        request: Request,
        usuario: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        if usuario.admin:
            LogAuditoriaService.registrar(
                db, usuario.id, chave, ip=_ip_do_pedido(request)
            )
            return usuario

        tem_permissao = False

        if usuario.perfil_id is not None:
            perfil = (
                db.query(Perfil)
                .filter(Perfil.id == usuario.perfil_id)
                .first()
            )
            tem_permissao = bool(
                perfil and chave in (perfil.permissoes or [])
            )

        if not tem_permissao:
            raise HTTPException(
                status_code=403,
                detail="Você não tem permissão para realizar essa ação.",
            )

        LogAuditoriaService.registrar(
            db, usuario.id, chave, ip=_ip_do_pedido(request)
        )

        return usuario

    return dependencia


def exigir_admin_apos_primeiro_usuario(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        security_opcional
    ),
    db: Session = Depends(get_db),
):
    """Cadastro de usuário (POST /users/) só pode ficar aberto sem login
    enquanto a loja não tiver ninguém cadastrado ainda — é a tela
    "Comece Grátis" do primeiro acesso. A partir do segundo usuário em
    diante, exige um admin autenticado; sem essa checagem, qualquer um
    com acesso à rede do backend conseguia criar contas à vontade."""

    if db.query(User).count() == 0:
        return None

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Autenticação necessária.",
        )

    usuario = get_current_user(credentials, db)

    if not usuario.admin:
        raise HTTPException(
            status_code=403,
            detail="Apenas administradores podem cadastrar novos usuários.",
        )

    return usuario
