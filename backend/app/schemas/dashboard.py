from pydantic import BaseModel


class DashboardResponse(BaseModel):

    vendas_hoje: float

    vendas_hoje_qtd: int

    vendas_mes: float

    compras_hoje: float

    saldo_caixa: float

    contas_receber: float

    contas_pagar: float

    clientes: int

    fornecedores: int

    produtos: int

    estoque_baixo: int