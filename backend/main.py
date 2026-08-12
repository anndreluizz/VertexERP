import os
import secrets
import sys

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.pdv import router as pdv_router
from app.api.v1.contas_pagar import router as contas_pagar_router
from app.api.v1.contas_receber import router as contas_receber_router
from app.api.v1.movimento_caixa import router as movimento_caixa_router
from app.api.v1.caixa import router as caixa_router
from app.api.v1.vendas import router as vendas_router
from app.api.v1.compras import router as compras_router
from app.api.v1.fornecedores import router as fornecedores_router
from app.api.v1.produtos import router as produtos_router
from app.api.v1.categorias import router as categorias_router
from app.api.v1.clientes import router as clientes_router
from app.api.v1.users import router as users_router
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.estoque import router as estoque_router
from app.api.v1.financeiro import router as financeiro_router
from app.api.v1.fiado import router as fiado_router
from app.api.v1.configuracoes import router as configuracoes_router
from app.api.v1.relatorios import router as relatorios_router

app = FastAPI(
    title="Vertex ERP",
    description="Sistema ERP Empresarial",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "sistema": "Vertex ERP",
        "status": "online"
    }


@app.exception_handler(Exception)
def handle_generic_exception(request: Request, exc: Exception):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(dashboard_router)
app.include_router(clientes_router)
app.include_router(categorias_router)
app.include_router(produtos_router)
app.include_router(fornecedores_router)
app.include_router(compras_router)
app.include_router(vendas_router)
app.include_router(caixa_router)
app.include_router(movimento_caixa_router)
app.include_router(contas_receber_router)
app.include_router(contas_pagar_router)
app.include_router(pdv_router)
app.include_router(estoque_router)
app.include_router(financeiro_router)
app.include_router(fiado_router)
app.include_router(configuracoes_router)
app.include_router(relatorios_router)

# Quando empacotado com PyInstaller (--onefile), __file__ aponta pra dentro
# da pasta temporária de extração (sys._MEIPASS) — certo pra achar arquivos
# empacotados como alembic.ini/migrations (read-only), mas errado pra
# escrever algo que precisa sobreviver ao processo (ex.: PRIMEIRO_ACESSO.txt,
# que precisa ficar do lado do .exe de verdade, não sumir com a pasta temp).
ASSETS_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

# Raiz da instalação: pasta onde o VertexERP.exe (launcher) mora, não a
# pasta do VertexERP-Backend.exe em si — como é um build --onedir, o
# backend fica numa subpasta própria (VertexERP-Backend/), um nível abaixo
# da raiz de verdade da instalação. O launcher já sabe essa raiz e repassa
# via variável de ambiente; sem ela (rodando o backend sozinho, fora do
# launcher), cai pro dev ou pra pasta do próprio exe.
if os.getenv("VERTEXERP_INSTALL_DIR"):
    INSTALL_DIR = os.getenv("VERTEXERP_INSTALL_DIR")
elif getattr(sys, "frozen", False):
    INSTALL_DIR = os.path.dirname(sys.executable)
else:
    INSTALL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@app.on_event("startup")
def preparar_banco():
    """Roda num banco novo (ou desatualizado) sem precisar de comando
    manual — essencial pra instalar o sistema numa máquina nova.

    Pulado no banco de teste: o conftest.py monta o schema direto via
    Base.metadata (drop_all/create_all), sem passar pelo alembic — rodar
    migrações por cima quebraria com "relation already exists".
    """

    if os.getenv("DB_NAME") == "vertexerp_test":
        return

    _rodar_migracoes()
    _criar_admin_inicial_se_necessario()


def _rodar_migracoes():
    config = Config(os.path.join(ASSETS_DIR, "alembic.ini"))
    config.set_main_option(
        "script_location", os.path.join(ASSETS_DIR, "migrations")
    )
    command.upgrade(config, "head")


def _criar_admin_inicial_se_necessario():
    # Import tardio: evita ciclo de import na inicialização do módulo.
    from app.database.session import SessionLocal
    from app.models.user import User
    from app.schemas.user import UserCreate
    from app.services.user_service import UserService

    db = SessionLocal()

    try:
        if db.query(User).count() > 0:
            return

        email = "admin@vertexerp.com"
        senha = secrets.token_urlsafe(9)

        UserService.criar_usuario(
            db,
            UserCreate(nome="Administrador", email=email, senha=senha),
        )

        admin = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )
        admin.admin = True
        db.commit()

        caminho = os.path.join(INSTALL_DIR, "PRIMEIRO_ACESSO.txt")

        with open(caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write(
                "ACESSO INICIAL DO VERTEX ERP\n\n"
                f"E-mail: {email}\n"
                f"Senha: {senha}\n\n"
                "Guarde essa senha em local seguro. Ainda não existe uma "
                "tela pra trocar a senha pelo sistema — anote em outro "
                "lugar e apague este arquivo depois.\n"
            )
    finally:
        db.close()