# Interface (Frontend)

Aplicativo desktop em PySide6 (Qt para Python), em `frontend/`. Não há build/empacotamento configurado — roda direto com `python app.py` a partir da pasta `frontend/`.

## Fluxo de navegação

```
app.py
  └── telas/login.py (LoginWindow)
        └── ao logar com sucesso, abre:
        telas/principal.py (PrincipalWindow)
              ├── menu lateral fixo (QFrame + QPushButton)
              └── QStackedWidget com uma página por módulo:
                    Dashboard, PDV, Produtos, Clientes, Fornecedores,
                    Compras, Vendas, Caixa, Ajuste Estoque, Relatórios,
                    Configurações (placeholder)
```

Todas as páginas são instanciadas de uma vez no `__init__` de `PrincipalWindow` (não é lazy-loading) e ficam vivas por trás do `QStackedWidget`, mesmo quando não visíveis.

## Comunicação com o backend

`frontend/services/api.py` expõe um cliente HTTP minimalista (`get`/`post`/`put`/`delete`) usando `requests`, com um token JWT guardado numa variável global de módulo (`TOKEN`), setado por `login()` e enviado como `Authorization: Bearer` em toda chamada subsequente.

Cada módulo de domínio tem seu próprio arquivo de serviço em `frontend/services/` (`cliente_service.py`, `produto_service.py`, `venda_service.py` etc.), que só encapsula chamadas a endpoints específicos — nenhuma lógica de negócio mora aqui, só HTTP.

## Duas gerações de telas

O projeto está no meio de uma migração de padrão de UI. Ao mexer numa tela existente, primeiro identifique qual padrão ela já usa:

**Padrão antigo (ainda em uso em alguns diálogos de cadastro)**
- Cada tela implementa sua própria `QTableWidget`/`QDialog` do zero, com estilo, filtro e atalhos duplicados em cada arquivo.
- Exemplos remanescentes: `telas/cadastro_cliente.py`, `telas/cadastro_fornecedor.py`, `telas/cadastro_produto.py` (janelas de cadastro/edição).

**Padrão novo (telas de listagem)**
- `widgets/base/base_crud_window.py` (`BaseCRUDWindow`): classe base com título, campo de pesquisa, `CrudToolbar` (Novo/Editar/Excluir/Atualizar) e uma `StandardTable`. Subclasses implementam `carregar`, `filtrar`, `novo`, `editar`, `excluir`.
- Componentes reutilizáveis em `widgets/`: `tables/standard_table.py`, `toolbar/crud_toolbar.py`, `dialogs/message_dialog.py` (`Mensagem.sucesso/erro/aviso/confirmar`), `dialogs/pesquisa_window.py` (busca em modal), `cards/card.py` (usado no Dashboard e Relatórios).
- Telas que já usam esse padrão: `telas/produtos.py`, `telas/clientes.py`, `telas/fornecedores.py`, `telas/vendas.py`, `telas/ajuste_estoque.py`, `telas/relatorios.py`.
- **Os diálogos de cadastro (criar/editar um registro) continuam no estilo antigo mesmo nas telas já migradas** — só a tela de listagem foi migrada para `BaseCRUDWindow`. `BaseCadastroDialog` (`widgets/base/base_cadastro_dialog.py`) existe mas nenhuma tela o usa hoje.

**Atenção**: `widgets/fields/` (campos mascarados de CPF, CNPJ, telefone, e-mail, dinheiro, quantidade) e `widgets/buttons/` (botões salvar/cancelar reutilizáveis) são **arquivos vazios** — infraestrutura planejada e nunca implementada. Não assuma que existem sem checar.

## Telas específicas dignas de nota

- **PDV** (`telas/pdv.py`): tela dedicada de ponto de venda — não usa `BaseCRUDWindow` (fluxo de criação, não listagem). Busca produto, monta itens, abre `telas/pagamento.py` para escolher forma de pagamento e calcular troco, envia a venda.
- **Vendas** (`telas/vendas.py`): histórico das vendas feitas no PDV. Como vendas não têm edição (só cancelamento), o botão "Editar" da toolbar é reaproveitado como "Ver Itens" (mostra o detalhamento) e "Excluir" como "Cancelar Venda"; o botão "Novo" fica oculto (vendas só se criam pelo PDV).
- **Ajuste Estoque** (`telas/ajuste_estoque.py`): formulário de ajuste + histórico, não é uma tela de CRUD tradicional.
- **Relatórios** (`telas/relatorios.py`): mostra o fluxo de caixa consolidado (cards de saldo + tabela de lançamentos), com seletor de período.

## Como rodar

```
cd frontend
python app.py
```

Requer o backend rodando em `http://127.0.0.1:8000` (URL fixa em `services/api.py`, não configurável via `.env`).
