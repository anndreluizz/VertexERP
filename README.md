# Vertex ERP

ERP para pequenas e médias empresas do varejo brasileiro: PDV, estoque, compras, vendas, caixa e financeiro (contas a pagar/receber). Backend em FastAPI + PostgreSQL, frontend desktop em PySide6.

Veja [docs/01-visao-geral.md](docs/01-visao-geral.md) para uma descrição da arquitetura e dos módulos, e o `CLAUDE.md` na raiz para convenções de código e comandos usados no dia a dia de desenvolvimento.

## Estrutura do repositório

```
backend/     API FastAPI (ver backend/README.md)
frontend/    App desktop PySide6
database/    Mixins e utilitários de banco compartilhados (BaseModelMixin, AuditMixin, CodeGenerator)
docs/        Documentação (visão geral, requisitos, banco de dados, API, interface, roadmap)
```

## Setup rápido

Pré-requisitos: Python 3.13, PostgreSQL rodando localmente.

```bash
# ambiente virtual (na raiz do repo)
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt   # arquivo em UTF-16; resalve em UTF-8 se o pip reclamar
pip install PySide6 requests      # dependências do frontend, não listadas no requirements.txt
```

Configure `backend/.env` (veja `backend/README.md` para as variáveis necessárias), depois:

```bash
cd backend
alembic upgrade head
uvicorn main:app --reload
```

Em outro terminal, com o backend no ar:

```bash
cd frontend
python app.py
```

Login padrão: crie um usuário via `POST /users/` (não exige autenticação) ou use um já existente no banco.

## Testes

```bash
cd backend
pytest
```

Veja `backend/README.md` para detalhes sobre o banco de teste usado pela suíte.

## Documentação

| Arquivo | Conteúdo |
|---|---|
| [docs/01-visao-geral.md](docs/01-visao-geral.md) | Arquitetura e módulos do sistema |
| [docs/02-requisitos.md](docs/02-requisitos.md) | Regras de negócio implementadas, por módulo |
| [docs/03-banco-de-dados.md](docs/03-banco-de-dados.md) | Schema completo das tabelas e relacionamentos |
| [docs/04-api.md](docs/04-api.md) | Referência de todas as rotas da API |
| [docs/05-interface.md](docs/05-interface.md) | Estrutura do frontend desktop |
| [docs/06-roadmap.md](docs/06-roadmap.md) | O que foi corrigido, problemas conhecidos e o que falta |
