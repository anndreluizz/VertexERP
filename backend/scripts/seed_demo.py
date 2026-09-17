"""
Popula dados de demonstracao para a apresentacao da faculdade: alguns
produtos, dois clientes, abre caixa (se nao tiver um aberto) e registra
algumas vendas, pra Dashboard/Fluxo de Caixa ja aparecerem com numeros
reais antes mesmo de comecar a demo ao vivo.

Pre-requisito: já ter feito o primeiro acesso pelo app (tela "Comece
Grátis"), que cria o primeiro usuário (promovido a admin direto no
banco) e a loja. Sem isso o script não tem em quem/onde lançar os dados.

Rode com (a partir de backend/, com o .venv ativado):
    python scripts\\seed_demo.py
"""

from decimal import Decimal

from app.database.session import SessionLocal
from app.models.user import User
from app.models.loja import Loja
from app.schemas.produto import ProdutoCreate
from app.schemas.cliente import ClienteCreate
from app.schemas.caixa import CaixaCreate
from app.schemas.venda import VendaCreate, ItemVendaCreate
from app.enums.forma_pagamento import FormaPagamento
from app.services.produto_service import ProdutoService
from app.services.cliente_service import ClienteService
from app.services.caixa_service import CaixaService
from app.services.venda_service import VendaService
from app.repositories.caixa_repository import CaixaRepository

db = SessionLocal()

usuario = db.query(User).filter(User.admin.is_(True)).first()
if not usuario:
    raise SystemExit(
        "Nenhum usuário admin encontrado. Faça o primeiro acesso pelo "
        "app (tela 'Comece Grátis') antes de rodar este script."
    )

loja = db.query(Loja).filter(Loja.ativa.is_(True)).order_by(Loja.id).first()
loja_id = loja.id if loja else None

produtos_demo = [
    ("7001", "Refrigerante 2L", "10", "6.50", "9.90", 40, 10),
    ("7002", "Pao Frances (kg)", "12", "9.00", "14.90", 25, 5),
    ("7003", "Leite Integral 1L", "13", "4.20", "6.50", 60, 15),
    ("7004", "Cafe 500g", "14", "12.00", "18.90", 30, 8),
    ("7005", "Detergente 500ml", "15", "2.10", "3.90", 50, 10),
]

produtos_criados = []
for codigo, nome, categoria, custo, venda, estoque, minimo in produtos_demo:
    produto = ProdutoService.criar(
        db,
        ProdutoCreate(
            codigo=codigo,
            nome=nome,
            categoria=categoria,
            preco_custo=Decimal(custo),
            preco_venda=Decimal(venda),
            estoque=estoque,
            estoque_minimo=minimo,
        ),
        loja_id,
    )
    produtos_criados.append(produto)
    print(f"produto {codigo} - {nome}")

clientes_demo = [
    ("Joana Ferreira", "111.111.111-11", "11999990001"),
    ("Marcos Vinicius", "222.222.222-22", "11999990002"),
]

clientes_criados = []
for nome, cpf, telefone in clientes_demo:
    cliente = ClienteService.criar(
        db,
        ClienteCreate(nome=nome, cpf_cnpj=cpf, telefone=telefone),
    )
    clientes_criados.append(cliente)
    print(f"cliente {nome}")

caixa = CaixaRepository.buscar_aberto(db, usuario.id, loja_id)
if not caixa:
    caixa = CaixaService.abrir(
        db, CaixaCreate(saldo_inicial=Decimal("200.00")), usuario.id, loja_id
    )
    print("caixa aberto com saldo inicial de 200.00")
else:
    print("ja havia um caixa aberto, reaproveitando")

vendas_demo = [
    (FormaPagamento.DINHEIRO, None, [(0, 2), (2, 3)]),
    (FormaPagamento.PIX, None, [(1, 1), (4, 2)]),
    (FormaPagamento.PRAZO, clientes_criados[0].id, [(3, 1)]),
]

for forma, cliente_id, itens_idx_qtd in vendas_demo:
    itens = [
        ItemVendaCreate(
            produto_id=produtos_criados[idx].id,
            quantidade=qtd,
            valor_unitario=produtos_criados[idx].preco_venda,
        )
        for idx, qtd in itens_idx_qtd
    ]
    venda = VendaService.criar(
        db,
        VendaCreate(cliente_id=cliente_id, forma_pagamento=forma, itens=itens),
        usuario.id,
        loja_id,
    )
    print(f"venda #{venda.id} - {forma.value}")

print("seed de demonstracao concluido")
