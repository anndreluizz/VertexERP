# Roadmap

Este documento não é um planejamento de produto — é um registro do estado atual do projeto: o que foi corrigido, o que ainda falta, e problemas conhecidos que não foram endereçados.

## Corrigido recentemente

- Handler global de exceções em `main.py`: erros de negócio (`raise Exception(...)`) agora retornam `400` com mensagem legível, em vez de `500` genérico.
- `SECRET_KEY` do JWT deixou de ficar hardcoded no código-fonte, agora vem do `.env`.
- `app/repositories/conta_pagar_repository.py` usava o enum errado (`StatusContaReceber`) para filtrar contas a pagar — `listar_pagas()` nunca retornava nada.
- `migrations/env.py` não importava os models `ContaPagar`/`ContaReceber` — a próxima migração autogerada apagaria essas duas tabelas inteiras. Corrigido.
- `POST /users/` e `GET /users/` quebravam sempre (`AttributeError`) porque o código usava API do Pydantic v2 (`model_validate`/`model_dump`) com Pydantic v1 instalado.
- `app/schemas/caixa.py` usava `ConfigDict` (Pydantic v2) — sob Pydantic v1 isso criava um campo `model_config` espúrio no schema em vez de configurar `orm_mode`.
- `PUT /produtos/{id}` quebrava sempre — `ProdutoRepository.atualizar()` tinha assinatura incompatível com a chamada do service.
- **Módulo de Compras nunca funcionou**: o model `Compra` não tinha as colunas `forma_pagamento`/`data_vencimento` que o service tentava gravar. Adicionadas via migração.
- **Pagar conta / receber conta não persistia o lançamento no caixa**: `CaixaOperacaoService.registrar_movimento` usava `db.flush()` em vez de `db.commit()`, e como nenhum commit posterior cobria essa mudança, ela era descartada ao fechar a sessão. Corrigido para commitar.
- `contas_pagar.py`/`contas_receber.py`: as rotas de pagar/receber faziam `usuario["id"]`, mas `usuario` é um objeto ORM `User`, não um dict — corrigido para `usuario.id`.
- Módulos `estoque.py` e `financeiro.py` (antes arquivos vazios e órfãos) implementados: ajuste manual de estoque com histórico, e fluxo de caixa consolidado.
- Telas `Clientes` e `Fornecedores` migradas para o padrão `BaseCRUDWindow`.
- Suíte de testes automatizados criada do zero (`backend/app/tests/`, 98 testes cobrindo todos os módulos do backend, incluindo autorização e paginação).
- **Autorização por perfil implementada**: dependency `require_admin` (`app/auth/dependencies.py`) bloqueia ações sensíveis (excluir cliente/fornecedor/categoria/produto, cancelar compra/venda/conta a pagar/conta a receber, fechar caixa) para usuários com `admin=False`. Nova rota `PUT /users/{id}/admin` permite que um admin promova outro usuário — como não há autopromoção, o primeiro admin do sistema precisa ser definido direto no banco (feito para o usuário `admin@vertex.com` já existente). Nova rota `GET /users/me` permite ao frontend descobrir o próprio perfil; o frontend usa isso pra **esconder** (não só desabilitar) os botões de excluir/cancelar/fechar caixa quando o usuário logado não é admin (Produtos, Clientes, Fornecedores, Vendas, Caixa).
- **Paginação adicionada** em todas as rotas de listagem (`skip`/`limit`, default 100, máximo 500) — ver `docs/04-api.md`. Todos os repositories de listagem sem `ORDER BY` explícito ganharam ordenação por `id` para que a paginação seja determinística. `listar_pendentes()` de contas a pagar/receber ficou de fora de propósito, pois alimenta o cálculo do fluxo de caixa e precisa do total real.

## Problemas conhecidos, não corrigidos

- **Pydantic v1 real, mas parte do código foi escrita como se fosse v2** — vale revisar o restante dos schemas (`app/schemas/*.py`) em busca de outros usos de API v2 que ainda não geraram erro por falta de cobertura de teste/uso.
- `datetime.utcnow()` está deprecated (aparece em warnings em quase todo `criar()`/`atualizar()` dos services) — a migração para `datetime.now(timezone.utc)` não foi feita.
- Aviso do SQLAlchemy sobre relacionamento sobreposto entre `Produto.itens_venda` e `ItemVenda.produto` (faltando `back_populates`/`overlaps`) — não corrigido, é só um `SAWarning`, não quebra nada.
- `POST /produtos/` tem um comentário `# TESTE TEMPORÁRIO` e removeu o `response_model` "pra descobrir onde está o erro de serialização" — parece uma investigação que ficou incompleta; vale revisar se ainda é necessário.
- Duplicidade de código de nome de produto (`codigo` único) não tem tratamento amigável — um `IntegrityError` do Postgres vaza como mensagem técnica no `detail` (ao contrário de fornecedores, que tratam duplicidade de CNPJ de forma limpa).
- `requirements.txt` está em UTF-16 e só lista dependências do backend (PySide6/requests do frontend não estão lá).
- `widgets/fields/*` e `widgets/buttons/*` no frontend são arquivos vazios (infraestrutura planejada, nunca implementada) — não usar sem antes escrever o conteúdo.
- `widgets/base/base_cadastro_dialog.py` não é usado por nenhuma tela — os diálogos de cadastro continuam no estilo manual antigo.
- Enums `StatusVenda`, `StatusCompra`, `StatusCaixa`, `PerfilUsuario`, `TipoDocumento`: os quatro últimos são arquivos vazios; `StatusVenda` tem conteúdo mas não é usado em lugar nenhum (o campo `status` das vendas é string livre).
- Produto não tem relação real (FK) com Categoria, apesar de ambas as tabelas existirem.

## Não implementado

- Tela de **Configurações** no frontend (hoje é um placeholder).
- O frontend não tem nenhum controle de "próxima página" — toda tela de listagem simplesmente recebe os primeiros 100 registros da API. Catálogos/históricos que ultrapassem esse número ficam com o excedente invisível até que uma navegação de páginas (ou scroll infinito) seja implementada nas telas.
- Testes automatizados do frontend (a suíte criada cobre só o backend).
