# Requisitos

Este documento descreve o comportamento que o sistema efetivamente implementa hoje, organizado por módulo (engenharia reversa do código, não um documento de requisitos original do projeto).

## Autenticação e autorização
- Login por e-mail e senha (hash bcrypt), retorna JWT válido por `ACCESS_TOKEN_EXPIRE_MINUTES` (padrão 60 min).
- Toda rota da API (exceto criação de usuário e login) exige o token.
- Usuários têm um perfil binário: comum (`admin=False`, padrão de todo cadastro) ou administrador (`admin=True`).
- Ações destrutivas ou de cancelamento exigem administrador: excluir cliente/fornecedor/categoria/produto, cancelar compra/venda, cancelar conta a pagar/receber, e fechar caixa. Usuário comum que tentar recebe `403`.
- Um admin pode promover outro usuário a admin. Não existe autopromoção — o primeiro administrador do sistema precisa ser definido diretamente no banco de dados.

## Clientes
- Cadastro com nome (obrigatório), CPF/CNPJ, telefone e e-mail (opcionais na criação, mas únicos quando informados).
- Não permite dois clientes com o mesmo CPF/CNPJ.
- Exclusão é lógica: o cliente marcado como excluído continua no banco com `ativo=False` e some das telas de listagem padrão (que filtram por ativos).

## Fornecedores
- Cadastro com razão social e CNPJ obrigatórios; nome fantasia, contato e localização opcionais.
- CNPJ é único — tentativa de duplicar retorna erro explícito.
- Exclusão é física (remove o registro do banco).

## Categorias
- Cadastro simples (nome único + descrição opcional), usado hoje apenas como texto livre no campo `categoria` do produto — **não há vínculo real (FK)** entre produto e categoria.

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

## Compras
- Registro de compra vinculado a um fornecedor, com lista de itens (produto, quantidade, valor unitário).
- Ao finalizar, o estoque de cada produto é aumentado automaticamente.
- Compras a prazo exigem fornecedor e data de vencimento, e geram uma conta a pagar automaticamente.
- Cancelar uma compra devolve (reduz) o estoque dos itens e remove o registro.

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
- Podem ser criadas manualmente ou geradas automaticamente por uma compra/venda a prazo.
- Status: `PENDENTE` → `PAGO`/`RECEBIDO` ou `CANCELADO`.
- Não é possível cancelar uma conta já paga/recebida, nem pagar/receber uma conta já quitada.

## Dashboard
Resumo do dia atual: total vendido, total comprado, saldo do caixa aberto, total pendente a receber, total pendente a pagar, número de clientes ativos, fornecedores, produtos cadastrados e produtos com estoque baixo.

## Relatórios — Fluxo de Caixa
Combina o saldo do caixa aberto com as contas a pagar/receber pendentes cujo vencimento cai dentro de uma janela configurável (7/15/30/60/90 dias), projetando o saldo esperado ao fim do período.

## Fora do escopo atual
- Módulos de Vendas/Relatórios/Configurações mais avançados (o menu tem espaço reservado para "Configurações", ainda não implementado).
- Perfis de acesso/permissões diferenciadas por usuário.
- Relacionamento real entre produto e categoria (hoje é texto livre).
