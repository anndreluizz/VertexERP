from fastapi import FastAPI

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