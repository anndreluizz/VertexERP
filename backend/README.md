# Vertex ERP — Backend

API REST em FastAPI + SQLAlchemy 2.0, banco PostgreSQL, autenticação JWT.

## Requisitos

- Python 3.13
- PostgreSQL rodando localmente (ou acessível pela rede)

## Setup

1. Crie e ative o ambiente virtual na raiz do repositório (`../.venv`).
2. Instale as dependências:
   ```
   pip install -r ../requirements.txt
   ```
   (o arquivo está em UTF-16; se `pip` reclamar de encoding, resalve-o em UTF-8 antes de instalar)
3. Crie um arquivo `.env` nesta pasta com as variáveis abaixo (`.env.example.py` existe mas está vazio, não serve de template):
   ```
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=vertexerp
   DB_USER=postgres
   DB_PASSWORD=...
   SECRET_KEY=...
   JWT_ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=60
   DEBUG=True
   ```
4. Rode as migrações:
   ```
   alembic upgrade head
   ```

## Rodando a API

```
uvicorn main:app --reload
```

Serve em `http://127.0.0.1:8000`. Documentação interativa em `/docs` (Swagger) e `/redoc`.

## Migrações

```
alembic revision --autogenerate -m "descricao"
alembic upgrade head
```

**Importante**: novos models precisam ser importados manualmente em `migrations/env.py` (na seção `# ===== IMPORTAR TODOS OS MODELS =====`), ou o `--autogenerate` não vai enxergá-los — e pior, pode gerar uma migração que **apaga** as tabelas dos models esquecidos, por não os reconhecer no metadata. Sempre revise o arquivo de migração gerado antes de rodar `upgrade head`.

## Testes

```
pytest
```

Os testes usam um banco Postgres de teste separado (`vertexerp_test` por padrão, mesmo host/credenciais do `.env`), criado e populado automaticamente pela suíte (`app/tests/conftest.py`) — não é preciso configurar nada manualmente além de ter o Postgres do `.env` acessível. O schema do banco de teste é recriado do zero a cada execução da suíte.

Rodar um arquivo ou teste específico:
```
pytest app/tests/test_venda.py
pytest app/tests/test_venda.py::test_criar_venda_diminui_estoque
```

## Arquitetura

Estrutura em camadas, um arquivo por entidade por camada:

```
app/models/<entidade>.py         # SQLAlchemy (Mapped/mapped_column)
app/schemas/<entidade>.py        # Pydantic (v1) Create/Update/Response
app/repositories/<entidade>_repository.py   # métodos estáticos, só acesso a dados
app/services/<entidade>_service.py          # métodos estáticos, regra de negócio
app/api/v1/<entidade>.py         # APIRouter, registrado em main.py
```

Veja `docs/03-banco-de-dados.md` e `docs/04-api.md` na raiz do repositório para o schema completo e a lista de rotas.
