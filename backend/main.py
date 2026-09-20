import os
import sys

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.pdv import router as pdv_router
from app.api.v1.contas_pagar import router as contas_pagar_router
from app.api.v1.contas_receber import router as contas_receber_router
from app.api.v1.categorias_despesa import (
    router as categorias_despesa_router,
)
from app.api.v1.centros_custo import (
    router as centros_custo_router,
)
from app.api.v1.plano_contas import (
    router as plano_contas_router,
)
from app.api.v1.extrato_bancario import (
    router as extrato_bancario_router,
)
from app.api.v1.movimento_caixa import router as movimento_caixa_router
from app.api.v1.caixa import router as caixa_router
from app.api.v1.vendas import router as vendas_router
from app.api.v1.produtos import router as produtos_router
from app.api.v1.categorias import router as categorias_router
from app.api.v1.marcas import router as marcas_router
from app.api.v1.clientes import router as clientes_router
from app.api.v1.users import router as users_router
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.estoque import router as estoque_router
from app.api.v1.financeiro import router as fiado_router
from app.api.v1.financeiro_fluxo_caixa import (
    router as financeiro_fluxo_caixa_router,
)
from app.api.v1.relatorios import router as relatorios_router
from app.api.v1.configuracoes import router as configuracoes_router
from app.api.v1.notificacoes import router as notificacoes_router
from app.api.v1.aprovacoes import router as aprovacoes_router
from app.api.v1.lojas import router as lojas_router
from app.api.v1.fornecedores import router as fornecedores_router
from app.api.v1.compras import router as compras_router
from app.services.aviso_vencimento_service import iniciar_verificacao_diaria
from app.services.whatsapp_lembrete_service import (
    iniciar_verificacao_diaria as iniciar_lembrete_whatsapp,
)

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
app.include_router(marcas_router)
app.include_router(produtos_router)
app.include_router(vendas_router)
app.include_router(caixa_router)
app.include_router(movimento_caixa_router)
app.include_router(contas_pagar_router)
app.include_router(contas_receber_router)
app.include_router(categorias_despesa_router)
app.include_router(centros_custo_router)
app.include_router(plano_contas_router)
app.include_router(extrato_bancario_router)
app.include_router(pdv_router)
app.include_router(estoque_router)
app.include_router(fiado_router)
app.include_router(financeiro_fluxo_caixa_router)
app.include_router(relatorios_router)
app.include_router(configuracoes_router)
app.include_router(notificacoes_router)
app.include_router(aprovacoes_router)
app.include_router(lojas_router)
app.include_router(fornecedores_router)
app.include_router(compras_router)

# Quando empacotado com PyInstaller (--onefile), __file__ aponta pra dentro
# da pasta temporária de extração (sys._MEIPASS) — certo pra achar arquivos
# empacotados como alembic.ini/migrations (read-only).
ASSETS_DIR = getattr(
    sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))
)


@app.on_event("startup")
def preparar_banco():
    """Roda num banco novo (ou desatualizado) sem precisar de comando
    manual — essencial pra instalar o sistema numa máquina nova.

    A criação do primeiro usuário/loja é feita pela própria tela de
    "Comece Grátis" do frontend (telas/cadastro_inicial.py), não aqui —
    por isso essa função só cuida do schema do banco.
    """

    if os.getenv("DB_NAME", "").startswith("vertexerp_test"):
        return

    _rodar_migracoes()

    # aviso diario de "contas vencidas/vencendo amanha" (ver
    # app/services/aviso_vencimento_service.py) -- so faz sentido numa
    # instalacao de verdade rodando continuamente, nao em teste.
    iniciar_verificacao_diaria()

    # lembrete diario de fiado parado via WhatsApp (ver
    # app/services/whatsapp_lembrete_service.py) -- so manda de
    # verdade se a integracao estiver configurada e ligada.
    iniciar_lembrete_whatsapp()


def _rodar_migracoes():
    config = Config(os.path.join(ASSETS_DIR, "alembic.ini"))
    config.set_main_option(
        "script_location", os.path.join(ASSETS_DIR, "migrations")
    )
    command.upgrade(config, "head")
