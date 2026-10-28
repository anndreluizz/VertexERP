from datetime import date, datetime
from decimal import Decimal

from app.schemas.base import Schema


# Tudo aqui e' PUBLICO (site da loja, sem login) -- nunca colocar custo,
# estoque exato, fornecedor ou qualquer dado interno nesses schemas.
# (max_pedido mostra no maximo LIMITE_PEDIDO: estoque grande nao vaza.)


class VitrineProduto(Schema):
    id: int
    slug: str
    codigo: str
    nome: str
    descricao: str | None = None
    categoria: str | None = None
    marca: str | None = None
    cor: str | None = None
    tamanho: str | None = None
    unidade: str = "UN"
    preco: Decimal
    # preenchido so' com promocao valendo hoje (ver Produto.em_promocao)
    preco_anterior: Decimal | None = None
    promocao_fim: date | None = None
    # "disponivel" | "esgotado" | "consulte" (kit: estoque e' dos componentes)
    disponibilidade: str
    # quantas unidades a sacola do site aceita: estoque, ate' LIMITE_PEDIDO
    # (ver vitrine_service); 1 = ultima unidade. Kit/sem estoque = 0
    max_pedido: int = 0
    destaque: bool = False
    novidade: bool = False
    fotos: list[str] = []


class VitrineCategoria(Schema):
    nome: str
    quantidade: int


class VitrineLoja(Schema):
    nome: str | None = None
    endereco: str | None = None


class VitrineResponse(Schema):
    gerado_em: datetime
    loja: VitrineLoja
    categorias: list[VitrineCategoria]
    # ids, do mais vendido pro menos (90 dias); vazio sem vendas
    mais_vendidos: list[int]
    produtos: list[VitrineProduto]
