"""
Script descartavel para limpar os clientes de teste criados ao
validar a tela de Clientes e o fluxo de fiado (Joao da Silva,
Maria Souza, Pedro Lima e o lancamento de fiado avulso deles).

Rode com:
    .venv\\Scripts\\python.exe scripts\\limpar_teste_clientes.py
"""

from app.database.session import SessionLocal
from app.models.cliente import Cliente
from app.models.movimento_fiado import MovimentoFiado

db = SessionLocal()

nomes_teste = [
    "Joao da Silva", "Maria Souza", "Pedro Lima",
    "andre luis", "carlos souza", "aline marques",
]

clientes = (
    db.query(Cliente)
    .filter(Cliente.nome.in_(nomes_teste))
    .all()
)

ids = [c.id for c in clientes]

db.query(MovimentoFiado).filter(
    MovimentoFiado.cliente_id.in_(ids)
).delete(synchronize_session=False)

db.query(Cliente).filter(Cliente.id.in_(ids)).delete(
    synchronize_session=False
)

db.commit()
print("limpeza concluida")
