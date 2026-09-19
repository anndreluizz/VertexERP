# Visão Geral

Vertex ERP é um sistema de gestão empresarial (ERP) voltado para pequenas e médias empresas do varejo brasileiro — cobrindo ponto de venda, controle de estoque, clientes (com crediário/fiado), financeiro (contas a pagar/receber), caixa, aprovações internas e operação com múltiplas lojas.

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

A lista abaixo reflete os routers hoje registrados em `backend/main.py` (fonte de verdade sobre o que está ativo).

| Módulo | O que faz |
|---|---|
| Autenticação | Login com e-mail/senha, emissão de JWT, refresh token, verificação em duas etapas |
| Usuários | Cadastro de usuários do sistema, perfil admin/não-admin, promoção de admin |
| Dashboard | Resumo do dia: vendas, saldo de caixa, contas a pagar/receber, alertas de estoque baixo |
| PDV | Ponto de venda: busca produto por código/código de barras, monta uma venda, finaliza com forma de pagamento (inclui PIX), gera comprovante e permite reenvio por WhatsApp/e-mail com histórico de envios |
| Vendas | Histórico de vendas (criadas pelo PDV), visualização de itens, cancelamento (devolve estoque) |
| Produtos / Categorias | Cadastro de produtos (preço de custo/venda, estoque, estoque mínimo) e categorias de produto |
| Clientes | Cadastro de clientes (CPF/CNPJ, contato), ficha do cliente com histórico/observações |
| Fiado (crediário) | Vendas fiadas por cliente, lançamento e baixa de fiado |
| Caixa | Abertura/fechamento de caixa, lançamentos manuais (sangria, suprimento), extrato de movimentos |
| Ajuste de Estoque | Entradas/saídas manuais de estoque fora do fluxo de venda (inventário, quebra, correção), com histórico |
| Contas a Pagar / Receber | Controle financeiro, com baixa automática no caixa ao pagar/receber; categorias de despesa próprias |
| Financeiro / Relatórios | Fluxo de caixa (projeção combinando caixa atual + contas pendentes) e demais relatórios |
| Aprovações | Fluxo de solicitação/aprovação para ações sensíveis, dependente de perfil admin |
| Notificações | Registro de dispositivos (device tokens) para envio de notificações |
| Lojas | Cadastro de lojas e estoque por loja, para operação com mais de uma unidade |
| Configurações | Parâmetros gerais do sistema, configuráveis pela tela de Configurações |

> **Compras e Fornecedores foram removidos** do domínio ativo (sem tela no frontend, sem router no backend). Os models correspondentes ainda existem no disco como código órfão — ver `CLAUDE.md`.

## Convenções do projeto

- Todo o código de domínio (nomes de variáveis, classes, mensagens de erro, textos de UI) é em português.
- Backend segue rigorosamente o padrão em camadas descrito acima — uma nova entidade deve ter seu `model`, `schema`, `repository`, `service` e rota em `api/v1/`, registrada em `main.py`.
- Frontend tem duas gerações de padrão de tela coexistindo: telas mais antigas com `QTableWidget`/`QDialog` construídos à mão, e uma base reutilizável mais nova (`BaseCRUDWindow` + `widgets/`) — ver [05-interface.md](05-interface.md).

Para detalhes de setup e comandos do dia a dia, veja o `README.md` na raiz e o `CLAUDE.md` (orientado a quem for desenvolver com assistência de IA).
