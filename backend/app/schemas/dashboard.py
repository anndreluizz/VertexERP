from pydantic import BaseModel


class DashboardResponse(BaseModel):

    vendas_hoje: float

    compras_hoje: float

    saldo_caixa: float

    contas_receber: float

    contas_pagar: float

    clientes: int

    fornecedores: int

    produtos: int

    estoque_baixo: int