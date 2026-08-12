"""
Script descartavel para limpar os dados de teste gerados ao validar
o fluxo de fiado (cliente teste, movimentos de fiado, e o
recebimento em dinheiro que entrou de verdade no caixa aberto).

Rode com:
    .venv\\Scripts\\python.exe scripts\\limpar_teste_fiado.py
"""

from app.database.session import SessionLocal
from app.models.cliente import Cliente
from app.models.movimento_fiado import MovimentoFiado
from app.models.movimento_caixa import MovimentoCaixa
from app.models.caixa import Caixa

db = SessionLocal()

# reverte o recebimento fiado EM DINHEIRO (R$5) que entrou de
# verdade no caixa aberto durante o teste
movimento_dinheiro = (
    db.query(MovimentoCaixa)
    .filter(MovimentoCaixa.id == 18)
    .first()
)

if movimento_dinheiro:
    caixa = (
        db.query(Caixa)
        .filter(Caixa.id == movimento_dinheiro.caixa_id)
        .first()
    )
    if caixa:
        caixa.saldo_final -= movimento_dinheiro.valor
        db.add(caixa)

db.query(MovimentoCaixa).filter(
    MovimentoCaixa.id.in_([18, 19])
).delete(synchronize_session=False)

db.query(MovimentoFiado).filter(
    MovimentoFiado.cliente_id == 2
).delete()

db.query(Cliente).filter(Cliente.id == 2).delete()

db.commit()
print("limpeza concluida")
