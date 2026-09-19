# API

Backend FastAPI, servido em `http://127.0.0.1:8000` por padrão (`uvicorn main:app`). Toda rota (exceto `POST /users/`, usado para criar o primeiro usuário) exige um JWT Bearer obtido em `/auth/login`.

## Autenticação

Todas as rotas abaixo, salvo indicação contrária, exigem o header:

```
Authorization: Bearer <token>
```

O token é emitido por `POST /auth/login` e expira em `ACCESS_TOKEN_EXPIRE_MINUTES` (padrão 60 min, configurável no `.env`).

## Formato de erro

A maioria dos erros de regra de negócio (`raise Exception("mensagem")` nos services) é convertida por um handler global em `main.py` para:

```json
{ "detail": "mensagem legível para o usuário" }
```
com status `400`. Erros que já são `HTTPException` explícitas (ex.: 404 de "não encontrado", 409 de CNPJ duplicado) mantêm seu status original.

## Autorização por perfil

Todo usuário tem um campo `admin: bool` (`false` por padrão em `POST /users/`). Ações sensíveis exigem `admin=True` — usuários comuns recebem `403 {"detail": "Apenas administradores podem realizar esta ação."}`. Rotas marcadas com 🔒 na tabela abaixo exigem admin.

Como não existe autopromoção, o **primeiro** usuário admin do sistema precisa ser definido diretamente no banco (`UPDATE users SET admin = true WHERE email = '...'`). A partir daí, um admin pode promover outros usuários por `PUT /users/{id}/admin`.

## Paginação

Toda rota de listagem (marcada com 📄 na tabela abaixo) aceita os parâmetros de query:

| Parâmetro | Default | Limites |
|---|---|---|
| `skip` | `0` | ≥ 0 |
| `limit` | `100` | 1 a 500 |

Exemplo: `GET /produtos/?skip=100&limit=50` retorna os registros 101–150. Sem parâmetros, o comportamento é o mesmo de antes da paginação existir (primeiros 100 registros).

**Exceção**: `GET /contas-pagar/pendentes` e `GET /contas-receber/pendentes` **não são paginadas** de propósito — essas duas listas alimentam o cálculo do fluxo de caixa (`GET /financeiro/fluxo-caixa`), que precisa do total real de contas pendentes, não só da primeira página.

**Limitação conhecida**: o frontend desktop ainda não tem controles de "próxima página" em nenhuma tela. Pra compensar isso, os services de `produtos`, `clientes`, `vendas` e `caixa` já fazem um loop interno buscando todas as páginas da API automaticamente (não ficam mais presos a 100). Os services de `contas_pagar`, `contas_receber`, `users`, `movimento_caixa` e `estoque` ainda fazem uma única chamada, então ficam presos aos 100 primeiros registros em lojas com mais que isso (ver `docs/06-roadmap.md`).

**Módulos sem paginação nenhuma**: `categorias-despesa`, `fiado`, `aprovações` e `lojas` (documentados abaixo) não aceitam `skip`/`limit` — os repositories correspondentes fazem `listar()` sem `.limit()`, ou seja, **sempre retornam todas as linhas**, sem risco de corte, mas também sem proteção nenhuma contra uma tabela muito grande no futuro.

## Rotas por módulo

### Auth — `/auth`
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/auth/login` | não | `{email, senha}` → `{access_token, token_type}` |

### Usuários — `/users`
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/users/` | não | Cria usuário (`nome`, `email`, `senha`); sempre criado com `admin=false` |
| GET | `/users/` 📄 | sim | Lista usuários |
| PUT | `/users/{id}/admin` 🔒 | admin | `{admin: bool}` — promove/rebaixa outro usuário |

### Dashboard — `/dashboard`
| Método | Rota | Descrição |
|---|---|---|
| GET | `/dashboard/` | Resumo agregando vendas/compras do dia, saldo do caixa aberto, totais de contas a pagar/receber pendentes, contagem de clientes ativos/fornecedores/produtos e produtos com estoque baixo |

### Clientes — `/clientes`
| Método | Rota | Descrição |
|---|---|---|
| POST | `/clientes/` | Cria cliente. Erro se `cpf_cnpj` já cadastrado |
| GET | `/clientes/` 📄 | Lista todos (inclusive inativos) |
| GET | `/clientes/{id}` | Busca por id |
| PUT | `/clientes/{id}` | Atualiza (`nome` e `ativo` obrigatórios no payload) |
| DELETE | `/clientes/{id}` 🔒 | **Soft-delete** (`ativo=False`) |

### Fornecedores e Compras — **removidos**

`/fornecedores` e `/compras` existiam nesta doc mas **não existem mais** — os routers `fornecedores_router`/`compras_router` não são registrados em `main.py` (módulo desativado a pedido do usuário). Os models `Fornecedor`/`Compra`/`ItemCompra` ainda existem no banco/código mas estão órfãos — não trate como domínio ativo (ver `CLAUDE.md`).

### Categorias (de produto) — `/categorias`
| Método | Rota | Descrição |
|---|---|---|
| POST | `/categorias/` | Cria. Nome duplicado → erro |
| GET | `/categorias/` 📄 | Lista |
| GET | `/categorias/{id}` | Busca por id |
| PUT | `/categorias/{id}` | Atualiza campos parciais |
| DELETE | `/categorias/{id}` 🔒 | **Hard-delete** |

### Produtos — `/produtos`
| Método | Rota | Descrição |
|---|---|---|
| GET | `/produtos/` 📄 | Lista |
| GET | `/produtos/{id}` | Busca (404 se não existir) |
| POST | `/produtos/` | Cria (`201`) |
| PUT | `/produtos/{id}` | Atualiza (payload precisa dos campos completos, schema não usa `exclude_unset`) |
| DELETE | `/produtos/{id}` 🔒 | **Hard-delete** |

### PDV — `/pdv`
| Método | Rota | Descrição |
|---|---|---|
| GET | `/pdv/produto/{codigo}` | Busca produto por `codigo` ou `codigo_barras`. 400 se não encontrado |

### Vendas — `/vendas`
| Método | Rota | Descrição |
|---|---|---|
| GET | `/vendas/` 📄 | Lista |
| GET | `/vendas/{id}` | Busca (404) |
| POST | `/vendas/` | Cria (`201`) com itens; **baixa o estoque**; erro se estoque insuficiente; se `forma_pagamento="PRAZO"`, gera uma `ContaReceber` |
| DELETE | `/vendas/{id}` 🔒 | Cancela: **devolve o estoque** e faz hard-delete |

Mesmo formato de payload das compras, mas com `cliente_id` (opcional) e `desconto`.

### Caixa — `/caixa`
| Método | Rota | Descrição |
|---|---|---|
| POST | `/caixa/abrir` | `{saldo_inicial}`. Erro se já existe caixa aberto |
| POST | `/caixa/fechar` 🔒 | Fecha o caixa aberto. Erro se não há nenhum |
| GET | `/caixa/aberto` | Retorna o caixa aberto atual, ou `null` |

### Movimentos de Caixa — `/movimentos-caixa`
| Método | Rota | Descrição |
|---|---|---|
| POST | `/movimentos-caixa/` | Lança movimento manual (`tipo`, `descricao`, `valor`) no caixa aberto. Erro se não há caixa aberto |
| GET | `/movimentos-caixa/` 📄 | Lista todos |
| GET | `/movimentos-caixa/caixa/{caixa_id}` 📄 | Lista de um caixa específico |
| GET | `/movimentos-caixa/tipo/{tipo}` 📄 | Filtra por tipo |

### Contas a Pagar — `/contas-pagar`
| Método | Rota | Descrição |
|---|---|---|
| POST | `/contas-pagar/` | Cria conta manualmente |
| GET | `/contas-pagar/` 📄 | Lista todas |
| GET | `/contas-pagar/pendentes` | Só pendentes — **não paginada** (ver seção Paginação) |
| GET | `/contas-pagar/pagas` 📄 | Só pagas |
| PUT | `/contas-pagar/{id}` | Atualiza campos parciais |
| POST | `/contas-pagar/{id}/pagar` | Marca como paga e lança `PAGAMENTO` no caixa aberto (exige caixa aberto) |
| POST | `/contas-pagar/{id}/cancelar` 🔒 | Cancela (não permite se já paga) |

### Contas a Receber — `/contas-receber`
| Método | Rota | Descrição |
|---|---|---|
| POST | `/contas-receber/` | Cria conta manualmente (exige `cliente_id` existente) |
| GET | `/contas-receber/` 📄 | Lista todas |
| GET | `/contas-receber/pendentes` | Só pendentes — **não paginada** (ver seção Paginação) |
| GET | `/contas-receber/recebidas` 📄 | Só recebidas |
| GET | `/contas-receber/cliente/{cliente_id}` 📄 | Filtra por cliente |
| PUT | `/contas-receber/{id}` | Atualiza campos parciais |
| POST | `/contas-receber/{id}/receber` | Marca como recebida e lança `RECEBIMENTO` no caixa aberto (exige caixa aberto) |
| POST | `/contas-receber/{id}/cancelar` 🔒 | Cancela (não permite se já recebida) |

### Categorias de Despesa — `/categorias-despesa`
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/categorias-despesa/` | sim | Lista todas (sem paginação, ver nota acima) |
| POST | `/categorias-despesa/` | sim | Cria |
| PUT | `/categorias-despesa/{id}` | sim | Atualiza |
| DELETE | `/categorias-despesa/{id}` 🔒 | admin | Exclui |

### Fiado — `/fiado`

Crediário de cliente (compra/pagamento avulso, fora do fluxo normal de venda/conta a receber). Implementado em `app/api/v1/financeiro.py`, apesar do nome do arquivo — não confundir com `/financeiro` (fluxo de caixa, seção própria abaixo).

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/fiado/movimentos` | sim | Cria movimento (`tipo`: COMPRA/PAGAMENTO, `cliente_id`, `valor`, ...) |
| GET | `/fiado/movimentos` | sim | Lista todos (sem paginação) |
| GET | `/fiado/movimentos/cliente/{cliente_id}` | sim | Lista de um cliente |
| PUT | `/fiado/movimentos/{id}` | sim | Atualiza; pode ajustar o caixa retroativamente (`caixa_ajustado` na resposta) |
| DELETE | `/fiado/movimentos/{id}` | sim | Exclui; idem, pode reverter ajuste no caixa |
| GET | `/fiado/saldo/{cliente_id}` | sim | Saldo devedor de um cliente |
| GET | `/fiado/saldos` | sim | Saldo devedor de **todos** os clientes com movimento, numa chamada só (evita N+1 na tela de Clientes) |
| GET | `/fiado/cliente/{cliente_id}` | sim | Ficha completa do cliente no fiado (usada por `frontend/telas/ficha_cliente.py`) |
| POST | `/fiado/pagamento` | sim | Atalho pra registrar pagamento sem passar `tipo`; **não** lança no caixa físico (para isso, usar `/fiado/movimentos` com `forma_pagamento`) |
| POST | `/fiado/compra` | sim | Atalho pra lançar uma compra fiado manual (ex.: dívida migrada de ficha em papel) |

### Relatórios — `/relatorios`
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/relatorios/vendas` 📄 | sim | Relatório de vendas com filtros (`data_inicio`, `data_fim` obrigatório, `cliente_id`, `produto_id`, `categoria`, `forma_pagamento`, `status`, `loja_id`) + ranking de top produtos (`top_produtos_limite`, `top_produtos_ordenar_por`) |
| GET | `/relatorios/comparativo-lojas` | sim | Compara vendas entre lojas num período (`data_inicio`, `data_fim` obrigatório) |

### Configurações — `/configuracoes`

Configuração única da loja (não é uma lista — um registro global).

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/configuracoes/` | sim | Busca a configuração atual |
| PUT | `/configuracoes/` 🔒 | admin | Atualiza |
| GET | `/configuracoes/logo` | sim | Retorna a logo cadastrada como imagem PNG (`404` se não houver) |

### Notificações — `/notificacoes`

Registro de device tokens (push notification), não uma caixa de notificações.

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/notificacoes/registrar-token` | sim | Registra um device token pro usuário logado |
| DELETE | `/notificacoes/token/{token}` | sim | Remove um token |

### Aprovações — `/aprovacoes`

Fila de solicitações que exigem aprovação de um admin (o que gera uma solicitação é definido em `SolicitacaoAprovacaoService`/pelos services de negócio, não neste router).

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/aprovacoes/pendentes` 🔒 | admin | Lista pendentes (sem paginação) |
| POST | `/aprovacoes/{id}/aprovar` 🔒 | admin | Aprova a solicitação |
| POST | `/aprovacoes/{id}/rejeitar` 🔒 | admin | Rejeita a solicitação |

### Lojas — `/lojas`

Suporte a múltiplas lojas (a maioria das outras rotas de listagem aceita um `loja_id` opcional pra filtrar, ex.: `/financeiro/fluxo-caixa`, `/relatorios/vendas`).

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/lojas/` | sim | Lista todas (sem paginação) |
| POST | `/lojas/` 🔒 | admin | Cria. Nome duplicado → erro |

### Estoque — `/estoque`
| Método | Rota | Descrição |
|---|---|---|
| POST | `/estoque/ajuste` | Ajuste manual (`produto_id`, `tipo`: ENTRADA/SAIDA, `quantidade`, `motivo`). Erro se saída maior que o estoque disponível |
| GET | `/estoque/movimentos` 📄 | Histórico completo |
| GET | `/estoque/movimentos/{produto_id}` 📄 | Histórico de um produto |

### Financeiro — `/financeiro`

Implementado em `app/api/v1/financeiro_fluxo_caixa.py` (não confundir com `app/api/v1/financeiro.py`, que apesar do nome implementa o router de `/fiado`, seção própria acima).

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/financeiro/fluxo-caixa?dias=N&loja_id=M` | sim | Saldo atual do caixa + contas a pagar/receber pendentes com vencimento nos próximos N dias (padrão 30) + saldo projetado. `loja_id` opcional filtra por loja; sem ele, usa a loja resolvida pro usuário logado (`resolver_loja_id`) |

## Documentação interativa

Como é FastAPI, `/docs` (Swagger) e `/redoc` já vêm prontos com o servidor rodando.
