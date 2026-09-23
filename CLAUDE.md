# CLAUDE.md

Este arquivo fornece orientações ao Claude Code (claude.ai/code) ao trabalhar com código neste repositório.

## Visão geral do projeto

Vertex ERP é um ERP empresarial brasileiro com backend em FastAPI e frontend desktop em PySide6 (Qt). O domínio cobre vendas (PDV/vendas), estoque (produtos), clientes, caixa e contas a pagar/receber. Todo o código de domínio (models, variáveis, endpoints, textos de UI) é escrito em português — mantenha essa convenção em código novo.

**Compras/Fornecedores foi removido** (a pedido do usuário, commit `remove: modulo de Fornecedores e Compras`): sem tela no frontend, sem router registrado em `main.py`. Os models `backend/app/models/compra.py`/`fornecedor.py` (e `item_compra.py`) ainda existem no disco mas estão órfãos — não trate como domínio ativo.

## Comandos

Backend (executar a partir de `backend/`, usando o `.venv` do repositório):
- Rodar a API pra uso com o frontend: **precisa de HTTPS**, mesmo em dev — `frontend/services/api.py` monta a URL sempre como `https://127.0.0.1:8000` (nunca `http://`), então `uvicorn main:app --reload` puro (HTTP) sobe a API mas o frontend não consegue falar com ela. Suba com certificado autoassinado, gerado/reaproveitado por `app/core/tls.py::garantir_certificado`:
  ```python
  import uvicorn
  from app.core.tls import garantir_certificado
  from main import app
  cert, key = garantir_certificado("certs")
  uvicorn.run(app, host="127.0.0.1", port=8000, ssl_certfile=cert, ssl_keyfile=key)
  ```
  (o pacote final usa o mesmo mecanismo, ver `backend/backend_entry.py`, só que na porta `58734` por padrão em vez de `8000` — ver comentário em `frontend/services/api.py` sobre `_PORTA_PADRAO`). `uvicorn main:app --reload` sem TLS ainda serve pra bater direto na API (`/docs`, testes manuais de rota via curl/Postman), só não serve pro frontend desktop.
- Rodar migrações: `alembic upgrade head`
- Criar uma migração: `alembic revision --autogenerate -m "descricao"` — **novos models precisam ser importados manualmente em `backend/app/models/__init__.py`**, ou o autogenerate não vai enxergá-los (`migrations/env.py` não importa cada model individualmente, só faz `from app import models`, então é o `__init__.py` do pacote que precisa listar o novo arquivo).
- Rodar testes: `pytest` (teste único: `pytest app/tests/test_venda.py::nome_do_teste`) — suíte real cobrindo todos os módulos do backend (194 testes). Usa um banco Postgres de teste separado (`vertexerp_test`, mesmas credenciais do `.env`), criado e recriado do zero automaticamente por `app/tests/conftest.py` a cada execução — não precisa de setup manual.

Frontend (executar a partir de `frontend/`):
- Rodar o app desktop: `python app.py` (requer o backend rodando em `https://127.0.0.1:8000` com TLS, ver acima; sem ele, o login falha com um diálogo "Servidor Offline" — e se o backend estiver em HTTP puro, falha com erro de SSL em vez disso)

Notas de setup:
- O `requirements.txt` na raiz está em UTF-16 e lista apenas dependências do backend (FastAPI, SQLAlchemy, Alembic, psycopg, python-jose, passlib, pytest, etc.). Pacotes exclusivos do frontend (`PySide6`, `requests`) não estão listados ali e precisam ser instalados separadamente.
- A configuração do backend vem de `backend/.env` (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `SECRET_KEY`, ...), carregada diretamente via `python-dotenv` + `os.getenv` em `app/database/session.py` e `migrations/env.py`. `app/config/settings.py` define uma classe `Settings` (pydantic), mas ela está sem uso atualmente — não assuma que é a fonte de verdade.
- Postgres é o único banco suportado (URL `postgresql+psycopg://` montada manualmente em dois lugares, citados acima).
- `backend/migrations/` (incluindo `versions/`) é normalmente versionado no git, não está no `.gitignore` — toda migração nova precisa ser commitada junto com o código que depende dela.

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
- Autorização: `app/auth/dependencies.get_current_admin` (mesmo módulo) bloqueia com `403` quem não tem `admin=True`. Usado em `Depends(get_current_admin)` no lugar de `Depends(get_current_user)` nas rotas destrutivas/de cancelamento (excluir cliente/fornecedor/categoria/produto, cancelar compra/venda/conta a pagar/receber, fechar caixa). Todo usuário novo nasce com `admin=False`; promover alguém exige já ser admin (`PUT /users/{id}/admin`) — o primeiro admin do sistema é definido direto no banco.
- Tipos de erro transversais ficam em `app/core/exceptions.py` (subclasses de `VertexException` com status/detail fixos), mas a maioria dos services ainda faz `raise Exception("mensagem")` diretamente, contando com o handler global do `main.py` — os dois padrões coexistem.
- Paginação: toda rota de listagem aceita `skip`/`limit` (default `0`/`100`, `limit` máximo `500`), propagados por rota → service → repository (`.offset(skip).limit(limit)` + `order_by` explícito, necessário para paginação determinística). Ao adicionar uma nova rota de listagem, siga esse padrão. Exceção: `listar_pendentes()` de contas a pagar/receber não é paginado, pois `FinanceiroService.fluxo_caixa` depende do total real para o cálculo — não adicione paginação ali sem revisar esse consumidor primeiro.
- Campos de status nos models (ex.: status de compra/venda/caixa/conta) são strings simples; as classes `Enum` correspondentes ficam em `app/enums/` como referência — os models não usam colunas `Enum` do SQLAlchemy.
- **Pydantic instalado é v1 (`1.10.26`), apesar de partes do código usarem API v2** (`model_validate`/`model_dump`, `ConfigDict`) — isso já causou bugs reais (rotas de `users` e o schema de `caixa`, corrigidos). Ao mexer em qualquer schema, use a API v1 (`class Config: orm_mode = True`, `.from_orm()`, `.dict()`), a menos que o pydantic seja atualizado deliberadamente para v2 em todo o projeto.
- O diretório `database/` na raiz do repo (**não** confundir com `backend/app/database/`) guarda mixins compartilhados do SQLAlchemy (`BaseModelMixin` para `ativo`/`criado_em`/`atualizado_em`, `AuditMixin` para `criado_por`/`atualizado_por`) e `CodeGenerator` para códigos sequenciais com prefixo — ainda não são aplicados de forma consistente nos models existentes, mas models novos devem usá-los quando precisarem de campos de auditoria/soft-delete.
- Veja `docs/06-roadmap.md` na raiz do repo para o histórico de bugs já corrigidos e problemas conhecidos ainda em aberto.

## Arquitetura do frontend (`frontend/`)

- Ponto de entrada `app.py` → `telas/login.py` (`LoginWindow`) → após login bem-sucedido abre `telas/principal.py` (`PrincipalWindow`), um `QMainWindow` com menu lateral e um `QStackedWidget` contendo um widget de página por módulo (dashboard, PDV, produtos, clientes, caixa, contas a pagar/receber, ...).
- `services/api.py` contém um cliente HTTP genérico mínimo (`login`/`get`/`post`/`put`/`delete`) com um `TOKEN` global de módulo, definido no login e enviado como Bearer. Os módulos de service por entidade (`services/cliente_service.py`, `services/produto_service.py`, ...) encapsulam isso para chamar endpoints específicos.
- **`frontend/design/` é o design system atual e a base de praticamente toda tela** (`tokens.py` — cor/raio/tipografia/sombra, com paleta clara e escura e `aplicar(escuro: bool)` pra trocar tema em runtime; `widgets.py` — componentes reutilizáveis `Card`/`CardKPI`/`BotaoPrimario`/`BotaoSucesso`/`BotaoPerigo`/`BotaoSecundario`/`Badge`/`Avatar`/`CampoTexto`; mais `theme.py`, `sidebar.py`, `header.py`, `icons.py`, `fonts.py`, `animations.py`, `responsive.py`, `charts.py`). 38 das ~39 telas reais importam `design/` — só `telas/cadastro_usuario.py` ficou pra trás, ainda em `QDialog` cru sem tokens. **Nunca escrever cor hex direto num stylesheet de tela** — sempre `tokens.PRIMARIA` etc. (exceção legítima: HTML de recibo/comprovante impresso, que deve ficar fixo preto-no-branco independente do tema; e paletas decorativas fixas tipo `_CORES_MONOGRAMA` de avatar, que não são texto/superfície da UI).
- **`BaseCRUDWindow`/`BaseCadastroDialog` (`widgets/base/`) não pegaram** — apesar do nome "padrão novo", só `telas/vendas.py` usa `BaseCRUDWindow`; todo o resto (`produtos.py`, `clientes.py`, `contas_pagar.py`, ...) é `QWidget`/`QDialog` construído à mão + `design/`. `BaseCadastroDialog` tem **zero telas usando**. Não assuma que é o padrão a seguir em tela nova sem confirmar — hoje o padrão de fato é "QWidget/QDialog manual estilizado com `design/`".
- `widgets/fields/*`: `money_field.py` (`MoneyField`), `quantity_field.py` (`QuantityField`), `cpf_field.py` (`CpfCnpjField` — máscara única que detecta CPF/CNPJ pela quantidade de dígitos), `phone_field.py` (`PhoneField`) e `email_field.py` (`EmailField`, validação de formato ao vivo via `utils.validacao.email_valido`) estão implementados e usados em `cadastro_cliente.py`/`configuracoes.py`/`gerenciar_usuarios.py`. Só `search_field.py` continua **vazio**. `widgets/buttons/*` também segue vazio — nunca implementado, não assuma que tem conteúdo.
- Os imports de widgets Qt usam caminhos absolutos com raiz em `frontend/` (ex.: `from telas.cadastro_cliente import ...`, `from design import tokens`), então `frontend/` precisa estar no `sys.path`/diretório de trabalho ao rodar o app.
