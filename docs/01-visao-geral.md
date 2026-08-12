# Visão Geral

Vertex ERP é um sistema de gestão empresarial (ERP) voltado para pequenas e médias empresas do varejo brasileiro — cobrindo ponto de venda, controle de estoque, compras, financeiro (contas a pagar/receber) e caixa.

## Arquitetura

O sistema é dividido em duas partes independentes que conversam por HTTP:

- **Backend** (`backend/`): API REST em FastAPI + SQLAlchemy 2.0, banco PostgreSQL. Autenticação por JWT. Arquitetura em camadas (model → schema → repository → service → rota) — um arquivo por entidade em cada camada.
- **Frontend** (`frontend/`): aplicativo desktop em PySide6 (Qt), que consome a API do backend via `requests`. Não há lógica de negócio no frontend — toda regra vive no backend.

```
┌──────────────────────┐        HTTP + JWT        ┌───────────────────────┐
│  Frontend (PySide6)  │ ───────────────────────▶ │  Backend (FastAPI)    │
│  telas/ services/    │ ◀─────────────────────── │  api/v1 → services →  │
│  widgets/            │                          │  repositories → models│
└──────────────────────┘                          └───────────┬───────────┘
                                                                │
                                                          PostgreSQL
```

## Módulos do sistema

| Módulo | O que faz |
|---|---|
| Autenticação | Login com e-mail/senha, emissão de JWT |
| Dashboard | Resumo do dia: vendas, compras, saldo de caixa, contas a pagar/receber, alertas de estoque baixo |
| PDV | Ponto de venda: busca produto por código/código de barras, monta uma venda, finaliza com forma de pagamento |
| Vendas | Histórico de vendas (criadas pelo PDV), visualização de itens, cancelamento (devolve estoque) |
| Produtos | Cadastro de produtos, com preço de custo/venda, estoque e estoque mínimo |
| Clientes | Cadastro de clientes (CPF/CNPJ, contato) |
| Fornecedores | Cadastro de fornecedores (CNPJ, contato) |
| Compras | Registro de compras de fornecedores, com baixa/alta automática de estoque e geração de conta a pagar quando a prazo |
| Caixa | Abertura/fechamento de caixa, lançamentos manuais (sangria, suprimento) |
| Ajuste de Estoque | Entradas/saídas manuais de estoque fora do fluxo de compra/venda (inventário, quebra, correção), com histórico |
| Contas a Pagar / Receber | Controle financeiro, com baixa automática no caixa ao pagar/receber |
| Relatórios (Fluxo de Caixa) | Projeção de saldo combinando caixa atual + contas a pagar/receber pendentes num período |

## Convenções do projeto

- Todo o código de domínio (nomes de variáveis, classes, mensagens de erro, textos de UI) é em português.
- Backend segue rigorosamente o padrão em camadas descrito acima — uma nova entidade deve ter seu `model`, `schema`, `repository`, `service` e rota em `api/v1/`, registrada em `main.py`.
- Frontend tem duas gerações de padrão de tela coexistindo: telas mais antigas com `QTableWidget`/`QDialog` construídos à mão, e uma base reutilizável mais nova (`BaseCRUDWindow` + `widgets/`) — ver [05-interface.md](05-interface.md).

Para detalhes de setup e comandos do dia a dia, veja o `README.md` na raiz e o `CLAUDE.md` (orientado a quem for desenvolver com assistência de IA).
