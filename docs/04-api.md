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

**Limitação conhecida**: o frontend desktop ainda não tem controles de "próxima página" em nenhuma tela — ele simplesmente recebe os primeiros 100 registros de cada listagem. Para catálogos/históricos que ultrapassem esse número, os registros excedentes ficam invisíveis na UI até que uma navegação de páginas seja implementada no frontend (ver `docs/06-roadmap.md`).

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

### Fornecedores — `/fornecedores`
| Método | Rota | Descrição |
|---|---|---|
| POST | `/fornecedores/` | Cria fornecedor. CNPJ duplicado → `409` |
| GET | `/fornecedores/` 📄 | Lista todos |
| GET | `/fornecedores/{id}` | Busca por id (404 se não existir) |
| PUT | `/fornecedores/{id}` | Atualiza |
| DELETE | `/fornecedores/{id}` 🔒 | **Hard-delete** |

### Categorias — `/categorias`
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

### Compras — `/compras`
| Método | Rota | Descrição |
|---|---|---|
| POST | `/compras/` | Cria compra com itens; **aumenta o estoque** dos produtos; se `forma_pagamento="PRAZO"`, gera uma `ContaPagar` automaticamente |
| GET | `/compras/` 📄 | Lista |
| GET | `/compras/{id}` | Busca (404) |
| DELETE | `/compras/{id}` 🔒 | Cancela: **devolve o estoque** e faz hard-delete |

Payload de criação:
```json
{
  "fornecedor_id": 1,
  "observacao": "opcional",
  "forma_pagamento": "DINHEIRO | PIX | DEBITO | CREDITO | BOLETO | PRAZO",
  "data_vencimento": "obrigatório se PRAZO",
  "itens": [{"produto_id": 1, "quantidade": 2, "valor_unitario": "10.00"}]
}
```

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

### Estoque — `/estoque`
| Método | Rota | Descrição |
|---|---|---|
| POST | `/estoque/ajuste` | Ajuste manual (`produto_id`, `tipo`: ENTRADA/SAIDA, `quantidade`, `motivo`). Erro se saída maior que o estoque disponível |
| GET | `/estoque/movimentos` 📄 | Histórico completo |
| GET | `/estoque/movimentos/{produto_id}` 📄 | Histórico de um produto |

### Financeiro — `/financeiro`
| Método | Rota | Descrição |
|---|---|---|
| GET | `/financeiro/fluxo-caixa?dias=N` | Saldo atual do caixa + contas a pagar/receber pendentes com vencimento nos próximos N dias (padrão 30) + saldo projetado |

## Documentação interativa

Como é FastAPI, `/docs` (Swagger) e `/redoc` já vêm prontos com o servidor rodando.
