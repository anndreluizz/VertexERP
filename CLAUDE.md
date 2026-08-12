# CLAUDE.md

Este arquivo fornece orientações ao Claude Code (claude.ai/code) ao trabalhar com código neste repositório.

## Visão geral do projeto

Vertex ERP é um ERP empresarial brasileiro com backend em FastAPI e frontend desktop em PySide6 (Qt). O domínio cobre vendas (PDV/vendas), compras, estoque (produtos), clientes/fornecedores, caixa e contas a pagar/receber. Todo o código de domínio (models, variáveis, endpoints, textos de UI) é escrito em português — mantenha essa convenção em código novo.

## Comandos

Backend (executar a partir de `backend/`, usando o `.venv` do repositório):
- Rodar a API: `uvicorn main:app --reload` (serve em `http://127.0.0.1:8000`)
- Rodar migrações: `alembic upgrade head`
- Criar uma migração: `alembic revision --autogenerate -m "descricao"` — **novos models precisam ser importados manualmente em `backend/migrations/env.py`**, ou o autogenerate não vai enxergá-los (veja a lista de imports já existente lá).
- Rodar testes: `pytest` (teste único: `pytest app/tests/test_venda.py::nome_do_teste`) — suíte real cobrindo todos os módulos do backend (~78 testes). Usa um banco Postgres de teste separado (`vertexerp_test`, mesmas credenciais do `.env`), criado e recriado do zero automaticamente por `app/tests/conftest.py` a cada execução — não precisa de setup manual.

Frontend (executar a partir de `frontend/`):
- Rodar o app desktop: `python app.py` (requer o backend FastAPI rodando em `127.0.0.1:8000`; sem ele, o login falha com um diálogo "Servidor Offline")

Notas de setup:
- O `requirements.txt` na raiz está em UTF-16 e lista apenas dependências do backend (FastAPI, SQLAlchemy, Alembic, psycopg, python-jose, passlib, pytest, etc.). Pacotes exclusivos do frontend (`PySide6`, `requests`) não estão listados ali e precisam ser instalados separadamente.
- A configuração do backend vem de `backend/.env` (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `SECRET_KEY`, ...), carregada diretamente via `python-dotenv` + `os.getenv` em `app/database/session.py` e `migrations/env.py`. `app/config/settings.py` define uma classe `Settings` (pydantic), mas ela está sem uso atualmente — não assuma que é a fonte de verdade.
- Postgres é o único banco suportado (URL `postgresql+psycopg://` montada manualmente em dois lugares, citados acima).
- `backend/migrations/` está no `.gitignore` — os arquivos de migração existem em disco mas não são versionados no git.

## Arquitetura do backend (`backend/app/`)

Estrutura em camadas rígida, um arquivo por entidade por camada — siga esse padrão exatamente ao adicionar uma nova entidade de domínio:

```
models/<entidade>.py                     Models SQLAlchemy (estilo 2.0, Mapped/mapped_column)
schemas/<entidade>.py                    Schemas Pydantic Create/Update/Response
repositories/<entidade>_repository.py    Métodos estáticos, db.query/add/commit puro — sem regra de negócio
services/<entidade>_service.py           Métodos estáticos, regras de negócio, levanta Exception simples em erro, chama o repository
api/v1/<entidade>.py                     APIRouter do FastAPI, um router por entidade, chama o service
```

- `backend/main.py` é o único lugar onde os routers são registrados (`app.include_router(...)`) — o router de uma entidade nova precisa ser incluído lá. Também é onde vive o handler global (`@app.exception_handler(Exception)`) que converte qualquer `raise Exception("mensagem")` de service em `400 {"detail": "mensagem"}` — sem ele, esses erros virariam `500` genéricos sem a mensagem de negócio.
- Cada módulo de router redeclara sua própria dependência local `get_db()` (duplicada em cada arquivo em vez de compartilhada), junto com `app.auth.dependencies.get_db`/`get_current_user`. Isso importa para testes: o override de `get_db` do FastAPI precisa ser aplicado em cada módulo individualmente (veja `MODULOS_COM_GET_DB` em `app/tests/conftest.py`).
- Autenticação: `app/auth/jwt.py` emite JWTs HS256, com `SECRET_KEY`/`JWT_ALGORITHM`/`ACCESS_TOKEN_EXPIRE_MINUTES` lidos do `.env` (não mais hardcoded). `app/auth/dependencies.get_current_user` decodifica o bearer token e carrega o `User` — o objeto retornado é uma instância ORM (`usuario.id`, não `usuario["id"]`).
- Autorização: `app/auth/dependencies.require_admin` (mesmo módulo) bloqueia com `403` quem não tem `admin=True`. Usado em `Depends(require_admin)` no lugar de `Depends(get_current_user)` nas rotas destrutivas/de cancelamento (excluir cliente/fornecedor/categoria/produto, cancelar compra/venda/conta a pagar/receber, fechar caixa). Todo usuário novo nasce com `admin=False`; promover alguém exige já ser admin (`PUT /users/{id}/admin`) — o primeiro admin do sistema é definido direto no banco.
- Tipos de erro transversais ficam em `app/core/exceptions.py` (subclasses de `VertexException` com status/detail fixos), mas a maioria dos services ainda faz `raise Exception("mensagem")` diretamente, contando com o handler global do `main.py` — os dois padrões coexistem.
- Paginação: toda rota de listagem aceita `skip`/`limit` (default `0`/`100`, `limit` máximo `500`), propagados por rota → service → repository (`.offset(skip).limit(limit)` + `order_by` explícito, necessário para paginação determinística). Ao adicionar uma nova rota de listagem, siga esse padrão. Exceção: `listar_pendentes()` de contas a pagar/receber não é paginado, pois `FinanceiroService.fluxo_caixa` depende do total real para o cálculo — não adicione paginação ali sem revisar esse consumidor primeiro.
- Campos de status nos models (ex.: status de compra/venda/caixa/conta) são strings simples; as classes `Enum` correspondentes ficam em `app/enums/` como referência — os models não usam colunas `Enum` do SQLAlchemy. Vários arquivos em `app/enums/` estão vazios (placeholders nunca implementados): `status_caixa.py`, `status_compra.py`, `perfil_usuario.py`, `tipo_documento.py`.
- **Pydantic instalado é v1 (`1.10.26`), apesar de partes do código usarem API v2** (`model_validate`/`model_dump`, `ConfigDict`) — isso já causou bugs reais (rotas de `users` e o schema de `caixa`, corrigidos). Ao mexer em qualquer schema, use a API v1 (`class Config: orm_mode = True`, `.from_orm()`, `.dict()`), a menos que o pydantic seja atualizado deliberadamente para v2 em todo o projeto.
- O diretório `database/` na raiz do repo (**não** confundir com `backend/app/database/`) guarda mixins compartilhados do SQLAlchemy (`BaseModelMixin` para `ativo`/`criado_em`/`atualizado_em`, `AuditMixin` para `criado_por`/`atualizado_por`) e `CodeGenerator` para códigos sequenciais com prefixo — ainda não são aplicados de forma consistente nos models existentes, mas models novos devem usá-los quando precisarem de campos de auditoria/soft-delete.
- Veja `docs/06-roadmap.md` na raiz do repo para o histórico de bugs já corrigidos e problemas conhecidos ainda em aberto.

## Arquitetura do frontend (`frontend/`)

- Ponto de entrada `app.py` → `telas/login.py` (`LoginWindow`) → após login bem-sucedido abre `telas/principal.py` (`PrincipalWindow`), um `QMainWindow` com menu lateral e um `QStackedWidget` contendo um widget de página por módulo (dashboard, PDV, produtos, clientes, fornecedores, compras, ...).
- `services/api.py` contém um cliente HTTP genérico mínimo (`login`/`get`/`post`/`put`/`delete`) com um `TOKEN` global de módulo, definido no login e enviado como Bearer. Os módulos de service por entidade (`services/cliente_service.py`, `services/fornecedor_service.py`, `services/compra_service.py`, ...) encapsulam isso para chamar endpoints específicos.
- **Duas gerações de UI coexistindo** — verifique qual padrão uma tela já usa antes de estendê-la:
  - Novo/reutilizável (telas de listagem): `widgets/base/base_crud_window.py` (`BaseCRUDWindow`), classe base no estilo template-method (subclasses definem `titulo`/`colunas` e implementam `carregar`/`filtrar`/`novo`/`editar`/`excluir`), apoiada por `widgets/tables/standard_table.py` (`StandardTable`), `widgets/toolbar/crud_toolbar.py` (`CrudToolbar`), `widgets/dialogs/message_dialog.py` (`Mensagem`), `widgets/dialogs/pesquisa_window.py`, `widgets/cards/card.py`. Já usado por `telas/produtos.py`, `telas/clientes.py`, `telas/fornecedores.py`, `telas/vendas.py`, `telas/ajuste_estoque.py`, `telas/relatorios.py`. Novas telas de listagem/CRUD devem seguir esse padrão.
  - Antigo/manual (diálogos de cadastro): mesmo nas telas já migradas para `BaseCRUDWindow`, os diálogos de criar/editar (`telas/cadastro_cliente.py`, `telas/cadastro_fornecedor.py`, `telas/cadastro_produto.py`) continuam com `QDialog` construído à mão. `widgets/base/base_cadastro_dialog.py` (`BaseCadastroDialog`) existe mas **nenhuma tela o usa**.
  - `widgets/fields/*` (campos mascarados de CPF/CNPJ/telefone/e-mail/dinheiro) e `widgets/buttons/*` são **arquivos vazios** — nunca implementados, não assuma que têm conteúdo.
- Os imports de widgets Qt usam caminhos absolutos com raiz em `frontend/` (ex.: `from telas.cadastro_cliente import ...`, `from widgets.tables.standard_table import ...`), então `frontend/` precisa estar no `sys.path`/diretório de trabalho ao rodar o app.
