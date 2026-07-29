"""
Script descartavel para limpar os dados de teste gerados ao validar
o fluxo de caixa (abrir/fechar, resumo, vendas dinheiro/pix) no
banco compartilhado de desenvolvimento.

Rode com:
    .venv\\Scripts\\python.exe scripts\\limpar_teste_caixa.py
"""

from app.database.session import SessionLocal
from app.models import User, Produto, Venda, ItemVenda, MovimentoEstoque
from app.models.caixa import Caixa
from app.models.movimento_caixa import MovimentoCaixa

db = SessionLocal()

for vid in (3, 4):
    db.query(ItemVenda).filter(ItemVenda.venda_id == vid).delete()
    db.query(Venda).filter(Venda.id == vid).delete()

db.query(MovimentoEstoque).filter(
    MovimentoEstoque.motivo.like("Venda #3%")
).delete()
db.query(MovimentoEstoque).filter(
    MovimentoEstoque.motivo.like("Venda #4%")
).delete()

produto = db.query(Produto).filter(Produto.id == 10).first()
if produto:
    produto.estoque += 2
    db.add(produto)

for cid in (1, 2, 5):
    db.query(MovimentoCaixa).filter(MovimentoCaixa.caixa_id == cid).delete()
    db.query(Caixa).filter(Caixa.id == cid).delete()

db.query(User).filter(
    User.email == "teste.caixa@vertexerp.com"
).delete()

db.commit()
print("limpeza concluida")
