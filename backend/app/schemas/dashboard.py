from pydantic import BaseModel


class VendaPorDia(BaseModel):

    data: str

    total: float


class DashboardResponse(BaseModel):

    vendas_hoje: float

    vendas_ontem: float

    compras_hoje: float

    saldo_caixa: float

    contas_receber: float

    contas_pagar: float

    total_fiado_devedor: float

    clientes: int

    fornecedores: int

    produtos: int

    estoque_baixo: int

    vendas_ultimos_7_dias: list[VendaPorDia]