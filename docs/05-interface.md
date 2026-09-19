# Interface (Frontend)

Aplicativo desktop em PySide6 (Qt para Python), em `frontend/`. Não há build/empacotamento configurado neste diretório (o pacote final distribuído em produção é gerado à parte); aqui roda direto com `python app.py` a partir da pasta `frontend/`.

## Fluxo de navegação

```
app.py
  └── telas/login.py (LoginWindow)
        ├── telas/verificar_2fa.py (Verificar2FADialog), se a conta tiver 2FA
        ├── telas/conectar_servidor.py / cadastro_inicial.py / cadastrar_loja.py,
        │     fluxo de primeiro acesso (sem servidor configurado ainda / sem loja cadastrada)
        └── ao logar com sucesso, abre:
        telas/principal.py (PrincipalWindow)
              ├── menu lateral fixo (QFrame + QPushButton)
              └── QStackedWidget com uma página por módulo:
                    Dashboard, Visão Geral, PDV, Caixa, Produtos, Clientes,
                    Contas a Pagar, Ajuste Estoque, Relatórios, Configurações
```

Todas as páginas são instanciadas de uma vez no `__init__` de `PrincipalWindow` (não é lazy-loading) e ficam vivas por trás do `QStackedWidget`, mesmo quando não visíveis.

**Compras e Fornecedores não fazem parte da navegação** — removidos a pedido do usuário (ver CLAUDE.md). `telas/compra_window.py` e `telas/fornecedor_busca.py` ainda existem em disco mas não são importados por `principal.py` nem por nenhuma outra tela — são código órfão, não trate como funcionalidade ativa.

## Comunicação com o backend

`frontend/services/api.py` expõe um cliente HTTP minimalista (`get`/`post`/`put`/`delete`) usando `requests`, com um token JWT guardado numa variável global de módulo (`TOKEN`), setado por `login()` e enviado como `Authorization: Bearer` em toda chamada subsequente. A URL é sempre HTTPS (`https://127.0.0.1:<porta>`), nunca HTTP puro — a porta padrão é `58734` quando rodando como executável empacotado (`sys.frozen`) ou `8000` em modo dev, e pode ser sobrescrita pela variável de ambiente `VERTEXERP_PORT`.

Cada módulo de domínio tem seu próprio arquivo de serviço em `frontend/services/` (`cliente_service.py`, `produto_service.py`, `venda_service.py`, `caixa_service.py`, `movimento_fiado_service.py`, `movimento_caixa_service.py`, `conta_pagar_service.py`, `categoria_service.py`, `categoria_despesa_service.py`, `loja_service.py`, `financeiro_service.py`, `relatorio_service.py`, `estoque_service.py`, `aprovacao_service.py`, `comprovante_service.py`, `pix_service.py`, `user_service.py`, `pdv_service.py`, entre outros), que só encapsula chamadas a endpoints específicos — nenhuma lógica de negócio mora aqui, só HTTP. Serviços auxiliares fora do padrão HTTP puro: `ean_lookup.py` (consulta código de barras), `pix_utils.py` (geração de payload Pix), `impressora_termica_service.py` (impressão local), `tls_confianca.py` (confiança no certificado autoassinado do backend), `preferencias_service.py` (preferências salvas localmente), `cliente_analise.py` (métricas/analytics de cliente).

**Chamadas de rede não são mais 100% síncronas/bloqueantes.** `services/worker.py` oferece `rodar_em_thread()`, que roda uma chamada de API numa `QThread` separada e entrega o resultado de volta na thread principal via sinal Qt (evita travar a janela inteira durante a espera) — os callbacks (`ao_sucesso`/`ao_erro`/`ao_finalizar`) **precisam** ser métodos vinculados a um `QObject` (não lambda/função solta), senão rodam na worker thread por engano e derrubam o app se mexerem em widget. Também oferece `em_paralelo()`, que dispara várias chamadas independentes ao mesmo tempo (via `ThreadPoolExecutor`) em vez de em fila — útil em conexão de alta latência (ex.: terminal remoto via Tailscale). Nem toda tela adotou esse padrão ainda; ao mexer numa tela existente, confira se ela já usa `rodar_em_thread` antes de assumir que a chamada trava a UI.

## Duas gerações de telas

O projeto está no meio de uma migração de padrão de UI. Ao mexer numa tela existente, primeiro identifique qual padrão ela já usa:

**Padrão antigo (a maioria das telas hoje)**
- Cada tela implementa sua própria `QTableWidget`/`QWidget`/`QDialog` do zero, com estilo, filtro e atalhos duplicados em cada arquivo.
- É o padrão de fato hoje, não a exceção — `produtos.py`, `clientes.py`, `contas_pagar.py`, `caixa.py`, `dashboard.py`, `visao_geral.py`, `pdv.py`, `relatorios.py`, `configuracoes.py`, `ajuste_estoque.py`, entre outras.

**Padrão novo (pouco adotado)**
- `widgets/base/base_crud_window.py` (`BaseCRUDWindow`): classe base com título, campo de pesquisa, `CrudToolbar` (Novo/Editar/Excluir/Atualizar) e uma `StandardTable`. Subclasses implementam `carregar`, `filtrar`, `novo`, `editar`, `excluir`.
- Componentes reutilizáveis em `widgets/`: `tables/standard_table.py`, `toolbar/crud_toolbar.py`, `dialogs/message_dialog.py` (`Mensagem.sucesso/erro/aviso/confirmar`), `dialogs/pesquisa_window.py` (busca em modal), `cards/card.py` (usado no Dashboard e Relatórios).
- Hoje só `telas/vendas.py` usa `BaseCRUDWindow` de fato (ver CLAUDE.md) — não assuma que é o padrão predominante sem confirmar tela a tela.
- `BaseCadastroDialog` (`widgets/base/base_cadastro_dialog.py`) existe mas **nenhuma tela o usa** hoje, em nenhuma geração.

**Atenção**: `widgets/fields/` (campos mascarados de CPF/CNPJ, telefone, e-mail, dinheiro, quantidade) está implementado e em uso (`cadastro_cliente.py`, `configuracoes.py`, `gerenciar_usuarios.py`). `widgets/fields/search_field.py` e todo `widgets/buttons/*`, que antes existiam como arquivos vazios, **foram removidos do disco** — não existem mais, nem como placeholder.

## Telas por área

**Autenticação e setup inicial**
- `telas/login.py` (`LoginWindow`): tela de login, painel animado + ilustração.
- `telas/verificar_2fa.py` (`Verificar2FADialog`): segunda etapa de login quando a conta exige 2FA.
- `telas/conectar_servidor.py` (`ConectarServidorDialog`): configurar endereço do backend (terminal remoto).
- `telas/cadastro_inicial.py` (`CadastroInicialWindow`): primeiro acesso do sistema (sem usuário/loja ainda).
- `telas/cadastrar_loja.py` (`CadastrarLojaDialog`): cadastro de uma nova loja (suporte multi-loja).

**PDV e vendas**
- `telas/pdv.py` (`PDV`, + `VendasSuspensasDialog` interno): tela de ponto de venda — busca produto, monta itens, suspende/retoma vendas em andamento, abre pagamento. Não usa `BaseCRUDWindow` (fluxo de criação, não listagem).
- `telas/buscar_produto.py` (`BuscarProdutoDialog`, atalho F1): busca modal de produto a partir do PDV.
- `telas/selecionar_cliente.py` (`SelecionarClienteDialog`): vincular um cliente à venda (fiado, histórico).
- `telas/pagamento.py` (`PagamentoWindow`): escolher forma de pagamento e calcular troco.
- `telas/venda_concluida.py` (`VendaConcluidaDialog`): confirmação pós-venda.
- `telas/produto_criado.py` (`ProdutoCriadoDialog`): confirmação de cadastro rápido de produto direto do PDV.
- `telas/vendas.py`: histórico das vendas feitas no PDV — única tela usando `BaseCRUDWindow`; como vendas não têm edição (só cancelamento), "Editar" da toolbar vira "Ver Itens" e "Excluir" vira "Cancelar Venda"; "Novo" fica oculto (vendas só se criam pelo PDV).

**Caixa**
- `telas/caixa.py` (`Caixa`): tela principal do módulo caixa.
- `telas/abrir_caixa.py` (`AbrirCaixaWindow`) / `telas/fechar_caixa.py` (`FecharCaixaWindow`): abertura/fechamento com conferência de valores.
- `telas/caixa_bloqueado.py` (`CaixaBloqueadoDialog`): bloqueia operações quando não há caixa aberto.
- `telas/sangria.py` (`SangriaWindow`) / `telas/suprimento.py` (`SuprimentoWindow`): retirada e reforço de caixa.

**Clientes e fiado**
- `telas/clientes.py` (`Clientes`, + `ClienteCard`): listagem de clientes.
- `telas/cadastro_cliente.py` (`CadastroClienteDialog`): criar/editar cliente.
- `telas/ficha_cliente.py` (`FichaClienteDialog`): perfil/timeline do cliente, com três sub-diálogos — `LancarFiadoDialog` (lançar fiado), `RegistrarPagamentoDialog` (baixa de fiado), `LancarHaverDialog` (crédito a favor do cliente).

**Produtos e categorias**
- `telas/produtos.py` (`Produtos`, + `_CardKPIClicavel`): listagem de produtos.
- `telas/cadastro_produto.py` (`CadastroProdutoWindow`): criar/editar produto.
- `telas/gerenciar_categorias.py` (`GerenciarCategoriasDialog`): CRUD de categorias de produto.
- `telas/ajuste_estoque.py` (`AjusteEstoque`): formulário de ajuste + histórico, não é uma tela de CRUD tradicional.

**Financeiro (contas a pagar / despesas)**
- `telas/contas_pagar.py` (`ContasPagar`, + `DespesaCard`): listagem/gestão de contas a pagar.
- `telas/cadastro_despesa.py` (`CadastroDespesaDialog`): criar/editar uma despesa.
- `telas/pagamento_despesa.py` (`PagamentoDespesaDialog`): baixar/pagar uma despesa.
- `telas/gerenciar_categorias_despesa.py` (`GerenciarCategoriasDespesaDialog`): CRUD de categorias de despesa.

**Dashboard e relatórios**
- `telas/dashboard.py` (`Dashboard`): painel inicial.
- `telas/visao_geral.py` (`VisaoGeral`, + `GraficoDesempenho`, `CardMetrica`): página separada de indicadores/gráficos de desempenho.
- `telas/dashboard_personalizar.py` (`PersonalizarDashboardDialog`): escolher quais cards/widgets aparecem no dashboard.
- `telas/relatorios.py` (`Relatorios`, + `LinhaBarra`, `PainelSecao`): fluxo de caixa consolidado (cards de saldo + tabela de lançamentos), com seletor de período.

**Comprovantes e envio**
- `telas/comprovante_dialog.py` (`ComprovanteDialog`): exibe/gera comprovante não fiscal de uma venda.
- `telas/comprovante_acoes.py` (+ `_Executor`, `QObject` rodando em thread): ações sobre o comprovante (ex.: enviar), sem travar a UI.
- `telas/historico_envios.py` (`HistoricoEnviosDialog`): histórico de comprovantes/lembretes enviados (ligado a `services/pix_service.py`, `pix_utils.py` e a lembretes via WhatsApp).

**Administração**
- `telas/configuracoes.py` (`Configuracoes`, + `ItemMenuConfig`): tela de configurações — **não é mais um placeholder**, tem conteúdo real (menu de itens de configuração).
- `telas/gerenciar_usuarios.py` (`GerenciarUsuariosDialog`, + `NovoUsuarioDialog`, `RedefinirSenhaDialog`): CRUD de usuários e redefinição de senha por um admin.
- `telas/trocar_senha.py` (`TrocarSenhaDialog`): o próprio usuário logado troca a senha.

**Código órfão (não navegável, ainda em disco)**
- `telas/compra_window.py`, `telas/fornecedor_busca.py`: remanescentes do módulo de Compras/Fornecedores removido — sem `import` em `principal.py` ou qualquer outra tela.

## Como rodar

```
cd frontend
python app.py
```

Requer o backend rodando com HTTPS (nunca HTTP puro — ver `services/api.py`) em `127.0.0.1:8000` por padrão em modo dev (`_PORTA_PADRAO`), ou na porta indicada por `VERTEXERP_PORT` se definida.
