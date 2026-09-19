# Requisitos

Este documento descreve o comportamento que o sistema efetivamente implementa hoje, organizado por módulo (engenharia reversa do código, não um documento de requisitos original do projeto).

## Autenticação e autorização
- Login por e-mail e senha (hash bcrypt), retorna JWT válido por `ACCESS_TOKEN_EXPIRE_MINUTES` (padrão 60 min).
- Toda rota da API (exceto criação de usuário e login) exige o token.
- Usuários têm um perfil binário: comum (`admin=False`, padrão de todo cadastro) ou administrador (`admin=True`).
- Ações destrutivas ou de cancelamento exigem administrador: excluir cliente/categoria/produto, cancelar venda, cancelar conta a pagar/receber, e fechar caixa. Usuário comum que tentar recebe `403`.
- Um admin pode promover outro usuário a admin. Não existe autopromoção — o primeiro administrador do sistema precisa ser definido diretamente no banco de dados.

## Clientes
- Cadastro com nome (obrigatório), CPF/CNPJ, telefone e e-mail (opcionais na criação, mas únicos quando informados).
- Não permite dois clientes com o mesmo CPF/CNPJ.
- Exclusão é lógica: o cliente marcado como excluído continua no banco com `ativo=False` e some das telas de listagem padrão (que filtram por ativos).

## Fornecedores e Compras (removido)
Os módulos de Fornecedores e Compras foram **removidos do sistema** a pedido do usuário (sem router em `main.py`, sem tela no frontend). Os models `fornecedor.py`/`compra.py`/`item_compra.py` ainda existem em disco mas são código órfão — não tratar como domínio ativo nem como requisito.

## Categorias
- Cadastro simples (nome único + descrição opcional), usado hoje apenas como texto livre no campo `categoria` do produto — **não há vínculo real (FK)** entre produto e categoria.

## Categorias de Despesa
- Cadastro simples (nome único), usado para classificar contas a pagar. Sem vínculo (FK) confirmado com `ContaPagar` — funciona como rótulo.

## Produtos
- Cadastro com código (único), nome, preço de custo, preço de venda, estoque atual e estoque mínimo.
- Suporta código de barras opcional (único), usado na busca do PDV.
- Alerta de estoque baixo: produtos com `estoque <= estoque_minimo` aparecem no dashboard.
- Exclusão é física.

## PDV / Vendas
- Operador busca produto por código ou código de barras, monta uma lista de itens com quantidade, e finaliza informando forma de pagamento (dinheiro, PIX, débito, crédito, boleto, ou a prazo).
- Ao finalizar, o estoque de cada produto é baixado automaticamente.
- Vendas a prazo exigem um cliente vinculado e geram uma conta a receber automaticamente.
- Uma venda não pode ser criada se o estoque de algum item for insuficiente.
- Cancelar uma venda devolve o estoque de todos os itens e remove o registro (não é um "estorno" com histórico — a venda desaparece).

## Caixa
- Só pode haver um caixa aberto por vez em todo o sistema.
- Abrir caixa define um saldo inicial; o saldo final acompanha os lançamentos.
- Fechar caixa registra a data/hora de fechamento e muda o status.
- Lançamentos manuais (sangria = saída, suprimento = entrada) alteram o saldo final do caixa aberto.
- Pagamentos de contas a pagar e recebimentos de contas a receber geram lançamentos automáticos no caixa aberto — **ambas as operações exigem que exista um caixa aberto no momento**.

## Ajuste de Estoque
- Permite registrar entrada ou saída manual de estoque de um produto, com motivo livre (inventário, quebra, correção etc.), fora do fluxo normal de compra/venda.
- Mantém histórico completo por produto e geral.
- Não permite saída maior que o estoque disponível.

## Contas a Pagar / Contas a Receber
- Podem ser criadas manualmente ou geradas automaticamente por uma venda a prazo.
- Status: `PENDENTE` → `PAGO`/`RECEBIDO` ou `CANCELADO`.
- Não é possível cancelar uma conta já paga/recebida, nem pagar/receber uma conta já quitada.
- `ContaReceber` é uma tabela legada que não é mais alimentada — venda a prazo gera um `MovimentoFiado` direto (ver Fiado/Crediário abaixo); o saldo real a receber vem de lá, não dessa tabela.

## Fiado / Crediário
- Cada cliente tem um saldo devedor calculado a partir de lançamentos (`MovimentoFiado`): `COMPRA` (aumenta a dívida, gerado automaticamente por uma venda a prazo ou lançado manualmente), `PAGAMENTO` (reduz a dívida, opcionalmente batendo no caixa se informada uma forma de pagamento) e `HAVER` (crédito manual em favor do cliente — desconto, devolução — reduz a dívida sem nunca mexer no caixa).
- Cliente tem um `limite_credito` opcional; ao ultrapassá-lo numa compra a prazo, os administradores são notificados automaticamente. Sem limite definido, nunca dispara.
- Pagamento em dinheiro exige caixa aberto no momento; corrigir ou excluir um lançamento de pagamento já registrado ajusta (ou estorna) o caixa correspondente, avisando se não havia caixa aberto pra aplicar o ajuste automaticamente.
- Ficha do cliente: endpoint dedicado retorna saldo devedor + histórico completo de movimentos numa chamada só.
- Verificação diária em background: clientes com saldo devedor parado (sem nenhuma movimentação) há mais dias que o configurado recebem um lembrete automático por WhatsApp — só dispara se a integração e esse lembrete específico estiverem ligados em Configurações, e não renotifica antes de completar o mesmo intervalo desde o último aviso.

## Aprovações
- Fluxo genérico de "pedir aprovação" para ações sensíveis específicas (hoje: excluir cliente, cancelar conta a pagar) — em vez de bloquear direto pra usuário comum, abre uma solicitação `PENDENTE` e notifica os administradores.
- Um admin aprova (executa a ação de verdade e marca `APROVADA`) ou rejeita (`REJEITADA`) a solicitação; o solicitante é notificado do resultado. Solicitação já resolvida não pode ser reprocessada.
- Novos tipos de ação sensível exigem registrar um executor específico no backend — não é configurável via UI/banco.

## Multi-loja
- Sistema suporta múltiplas lojas cadastradas (`Loja`, nome único). Produto, Venda, ContaPagar e Caixa carregam `loja_id`.
- Estoque por produto é controlado por loja (`EstoqueLoja`) — o campo agregado `Produto.estoque` é a soma entre todas as lojas; alertas de estoque baixo e busca do PDV podem ser filtrados por loja específica.
- Dashboard e relatórios de vendas aceitam filtro por loja, incluindo um comparativo lado a lado entre todas as lojas ativas (mesmos KPIs, um conjunto por loja).

## Notificações
- Push via Firebase Cloud Messaging para dispositivos com token registrado (`DeviceToken`, um token por usuário/aparelho — token repetido atualiza o dono em vez de duplicar). Sem `FIREBASE_CREDENTIALS_PATH` configurado, o sistema simplesmente não envia (não derruba nada).
- Disparos automáticos: aprovação pendente/resolvida, cliente que passou do limite de crédito, recebimento de fiado, e duas verificações diárias em background — contas a pagar vencidas/vencendo amanhã, e clientes com fiado parado (ver acima).
- Envio de mensagens via WhatsApp (serviço próprio, `whatsapp_service.py`) usado hoje pelo lembrete automático de fiado parado.

## Configurações
- Registro único por instalação (`Configuracao`): dados da loja (nome, logo em base64) e parâmetros de integrações — ligar/desligar WhatsApp, ligar/desligar e definir o prazo (em dias) do lembrete automático de fiado parado.

## Comprovantes
- Todo envio de comprovante de venda (por e-mail, WhatsApp etc.) é registrado (`ComprovanteEnvio`) com canal, destino e status — inclusive quando falha, com o motivo do erro. Histórico nunca é apagado, serve de auditoria de "o cliente recebeu ou não".

## PDV — pesquisa rápida
Endpoint dedicado (separado da tela de cadastro de Produtos) usado pelo balcão: busca por código/código de barras exato ou por nome/código com `LIKE`, já considerando o estoque da loja do terminal quando informado.

## Dashboard
Resumo do dia (e comparativos), com suporte a filtro por loja: total vendido hoje/ontem/mês (+ série dos últimos 7 dias e série mensal dos últimos 6 meses), saldo somado dos caixas abertos, saldo devedor de fiado, contas a pagar pendentes/vencidas/vencendo hoje/pagas hoje, contagem de clientes e produtos, produtos com estoque baixo (por loja, quando filtrado). Ainda soma `Compra`/`Fornecedor` no cálculo (tabelas órfãs do módulo removido) — ver auditoria de roadmap.

## Relatórios
- **Vendas**: KPIs completos (receita, lucro, ticket médio, margem, clientes atendidos) com comparação automática contra o período anterior de mesma duração, série diária, top produtos (por quantidade ou valor), quebra por forma de pagamento (considerando vendas divididas em duas formas), e tabela detalhada paginada. Filtra por período, cliente, produto, categoria, forma de pagamento, status e loja.
- **Comparativo entre lojas**: os mesmos KPIs principais, um conjunto por loja ativa, lado a lado.
- **Fluxo de Caixa**: combina o saldo do caixa aberto com as contas a pagar/receber pendentes cujo vencimento cai dentro de uma janela configurável (7/15/30/60/90 dias), projetando o saldo esperado ao fim do período.

## Fora do escopo atual
- Compras e Fornecedores (removidos do sistema — ver seção acima).
- Relacionamento real (FK) entre produto e categoria, e entre conta a pagar e categoria de despesa (ambos hoje são texto livre/sem vínculo confirmado).
- Paginação de fato (parâmetro de "próxima página" na UI) nos módulos que ainda ficam presos ao limite padrão de 100 registros por chamada (categorias, contas a pagar/receber, usuários, lojas, movimentos, aprovações, estoque) — produtos, clientes, vendas e caixa já buscam tudo internamente.
