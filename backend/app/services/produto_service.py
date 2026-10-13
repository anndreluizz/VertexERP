import base64

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.produto import Produto
from app.models.produto_foto import ProdutoFoto
from app.models.historico_preco import HistoricoPreco
from app.repositories.produto_repository import ProdutoRepository
from app.repositories.estoque_loja_repository import EstoqueLojaRepository
from app.repositories.produto_foto_repository import ProdutoFotoRepository
from app.repositories.historico_preco_repository import (
    HistoricoPrecoRepository,
)
from app.schemas.produto import ProdutoCreate, ProdutoUpdate


def _sincronizar_foto_principal(db: Session, produto: Produto, imagem: bytes):
    """Mantem Produto.foto (campo legado) e a foto PRINCIPAL de
    produto_fotos em sincronia sempre que alguem salva pelo caminho
    antigo (foto_base64 direto no cadastro) -- assim quem so' usa uma
    foto (a grande maioria) nunca fica com produto_fotos vazio, e a
    galeria nova sempre reflete o que a tela de cadastro mostra como
    "a" foto do produto."""

    fotos = ProdutoFotoRepository.listar_por_produto(db, produto.id)
    principal = next((f for f in fotos if f.principal), None)

    if principal:
        principal.imagem = imagem
        ProdutoFotoRepository.atualizar(db, principal)
    else:
        ProdutoFotoRepository.criar(
            db,
            ProdutoFoto(
                produto_id=produto.id,
                imagem=imagem,
                ordem=ProdutoFotoRepository.maior_ordem(db, produto.id) + 1,
                principal=True,
            ),
        )


def _aplicar_estoque_por_loja(db: Session, produtos, loja_id: int):
    ids = [p.id for p in produtos]
    mapa_quantidade = EstoqueLojaRepository.quantidades_por_loja(
        db, ids, loja_id
    )
    mapa_minimo = EstoqueLojaRepository.minimos_por_loja(
        db, ids, loja_id
    )
    for produto in produtos:
        produto.estoque = mapa_quantidade.get(produto.id, 0)
        produto.estoque_minimo = mapa_minimo.get(
            produto.id, produto.estoque_minimo
        )
    return produtos


class ProdutoService:

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100, loja_id: int | None = None):
        produtos = ProdutoRepository.listar(db, skip, limit, loja_id)

        if loja_id is not None:
            produtos = _aplicar_estoque_por_loja(db, produtos, loja_id)

        return produtos

    @staticmethod
    def listar_variacoes(
        db: Session, produto_pai_id: int, loja_id: int | None = None
    ):
        variacoes = ProdutoRepository.listar_variacoes(db, produto_pai_id)

        if loja_id is not None:
            variacoes = _aplicar_estoque_por_loja(db, variacoes, loja_id)

        return variacoes

    @staticmethod
    def buscar(db: Session, produto_id: int, loja_id: int | None = None):
        produto = ProdutoRepository.buscar_por_id(db, produto_id)

        if produto is None:
            return None

        # produto exclusivo de outra loja (ver Produto.loja_id) nao
        # deve aparecer pra quem esta noutro terminal -- trata como nao
        # encontrado, mesmo padrao de listar()
        if (
            loja_id is not None
            and produto.loja_id is not None
            and produto.loja_id != loja_id
        ):
            return None

        if loja_id is not None:
            produto.estoque = EstoqueLojaRepository.quantidades_por_loja(
                db, [produto.id], loja_id
            ).get(produto.id, 0)
            produto.estoque_minimo = EstoqueLojaRepository.minimos_por_loja(
                db, [produto.id], loja_id
            ).get(produto.id, produto.estoque_minimo)

        return produto

    @staticmethod
    def criar(db: Session, dados: ProdutoCreate, loja_id: int | None = None):

        # numero curto no campo de codigo de barras (o "01" que a loja
        # inventa pra produto sem etiqueta) e' codigo interno, nao EAN
        cb = dados.codigo_barras
        if cb and cb.isdigit() and len(cb) <= 6 and dados.codigo in ("", cb):
            dados.codigo, dados.codigo_barras = cb.zfill(4), None

        # ponytail: dois cadastros no mesmo instante pegam o mesmo numero
        # e o segundo cai no "ja existe" -- basta salvar de novo
        if not dados.codigo:
            dados.codigo = str(
                ProdutoRepository.proximo_codigo_interno(db)
            ).zfill(4)

        condicoes = [Produto.codigo == dados.codigo]

        if dados.codigo_barras:
            condicoes.append(Produto.codigo_barras == dados.codigo_barras)

        # catalogo unico: produto novo nasce global (visivel em todas as
        # lojas, estoque separado por loja em EstoqueLoja) -- exclusivo
        # quebrava a transferencia (a loja destino nao enxergava o
        # produto). Duplicidade conta contra QUALQUER produto, inclusive
        # exclusivos antigos, pra nao ter dois "01" na mesma loja.
        existente = db.query(Produto).filter(or_(*condicoes)).first()

        if existente:
            if existente.codigo == dados.codigo:
                raise ValueError(
                    f'Já existe um produto com o código '
                    f'"{dados.codigo}".'
                )
            raise ValueError(
                f'Já existe um produto ("{existente.nome}") '
                f'cadastrado com esse código de barras.'
            )

        if dados.produto_pai_id is not None:
            pai = ProdutoRepository.buscar_por_id(db, dados.produto_pai_id)

            if not pai:
                raise Exception("Produto pai não encontrado.")

            if pai.produto_pai_id is not None:
                raise Exception(
                    "Uma variação não pode ser criada a partir de outra "
                    "variação."
                )

        campos = dados.dict(exclude={"foto_base64"})
        produto = Produto(**campos)

        if dados.foto_base64:
            produto.foto = base64.b64decode(dados.foto_base64)

        produto = ProdutoRepository.criar(db, produto)

        if dados.foto_base64:
            _sincronizar_foto_principal(db, produto, produto.foto)

        # semeia o estoque inicial na loja de quem cadastrou -- sem
        # isso, o proximo ajuste/venda feito em QUALQUER loja recalcula
        # produto.estoque como soma das linhas de EstoqueLoja que
        # existirem, e essa loja nova ainda nao tem nenhuma: o estoque
        # inicial digitado no cadastro sumiria (viraria 0) assim que
        # outra loja mexesse no produto primeiro.
        if loja_id is not None and produto.estoque:
            registro = EstoqueLojaRepository.obter_ou_criar(
                db, produto.id, loja_id
            )
            registro.quantidade = produto.estoque
            db.add(registro)
            db.commit()

        return produto

    @staticmethod
    def atualizar(
        db: Session,
        produto_id: int,
        dados: ProdutoUpdate,
        loja_id: int | None = None,
        usuario_id: int | None = None,
    ):
        produto = ProdutoRepository.buscar_por_id(db, produto_id)

        if not produto:
            return None

        preco_custo_anterior = produto.preco_custo
        preco_venda_anterior = produto.preco_venda

        # mesmo guard de visibilidade do buscar() -- terminal de uma
        # loja nao edita produto exclusivo de outra so' por adivinhar o
        # id
        if (
            loja_id is not None
            and produto.loja_id is not None
            and produto.loja_id != loja_id
        ):
            return None

        # exclude_unset: sem isso, todo campo que o formulario nao manda
        # (ex.: "ativo", que o dialogo de edicao nunca envia) volta pro
        # valor padrao do schema em vez de manter o que ja estava salvo
        # -- editar um produto desativado reativava ele sem querer.
        #
        # "estoque" sai do lote generico e vira um AJUSTE da loja de
        # quem editou (mesma logica de MovimentoEstoqueService) -- sem
        # isso, editar o produto sobrescrevia direto o agregado entre
        # lojas com o que a tela mostrava (que, pelo mesmo motivo, podia
        # nem ser o estoque real da loja de quem estava editando).
        if (
            dados.produto_pai_id is not None
            and dados.produto_pai_id != produto.produto_pai_id
        ):
            if dados.produto_pai_id == produto_id:
                raise Exception(
                    "Um produto não pode ser variação de si mesmo."
                )

            pai = ProdutoRepository.buscar_por_id(db, dados.produto_pai_id)

            if not pai:
                raise Exception("Produto pai não encontrado.")

            if pai.produto_pai_id is not None:
                raise Exception(
                    "Uma variação não pode ser criada a partir de outra "
                    "variação."
                )

        campos = dados.dict(exclude_unset=True, exclude={"foto_base64"})
        novo_estoque = campos.pop("estoque", None)

        # mesmo motivo do "estoque" acima: com loja_id resolvido, o
        # minimo editado na tela e' o minimo DAQUELA loja
        # (EstoqueLoja.estoque_minimo), nao o global -- sem isso,
        # editar o produto numa loja sobrescreveria o minimo global
        # que outras lojas ainda usam como fallback (ver
        # ProdutoService.listar/buscar).
        novo_estoque_minimo = campos.pop("estoque_minimo", None)

        # mesma checagem que ja existe em criar() -- codigo_barras e'
        # editavel na tela (o codigo em si nao, mas a API aceita
        # qualquer chamador). Sem isso, mudar pra um valor que ja
        # pertence a outro produto estoura um IntegrityError cru do
        # banco (unique constraint) em vez de uma mensagem legivel.
        for campo in ("codigo", "codigo_barras"):

            valor = campos.get(campo)

            if not valor or valor == getattr(produto, campo):
                continue

            existente = (
                db.query(Produto)
                .filter(
                    getattr(Produto, campo) == valor,
                    Produto.loja_id == produto.loja_id,
                    Produto.id != produto_id,
                )
                .first()
            )

            if existente:
                if campo == "codigo":
                    raise ValueError(
                        f'Já existe um produto com o código "{valor}".'
                    )
                raise ValueError(
                    f'Já existe um produto ("{existente.nome}") '
                    f'cadastrado com esse código de barras.'
                )

        for campo, valor in campos.items():
            setattr(produto, campo, valor)

        if novo_estoque is not None:
            if loja_id is not None:
                atual = EstoqueLojaRepository.obter_ou_criar(
                    db, produto.id, loja_id
                ).quantidade
                EstoqueLojaRepository.ajustar(
                    db, produto, loja_id, novo_estoque - atual
                )
            else:
                produto.estoque = novo_estoque

        if novo_estoque_minimo is not None:
            if loja_id is not None:
                registro = EstoqueLojaRepository.obter_ou_criar(
                    db, produto.id, loja_id
                )
                registro.estoque_minimo = novo_estoque_minimo
                db.add(registro)
            else:
                produto.estoque_minimo = novo_estoque_minimo

        if dados.foto_base64:
            produto.foto = base64.b64decode(dados.foto_base64)
            _sincronizar_foto_principal(db, produto, produto.foto)

        # so' registra historico quando o preco de fato mudou -- editar
        # o produto por outro motivo (nome, categoria, foto...) sem
        # mexer no preco nao deveria gerar entrada nenhuma
        preco_mudou = (
            produto.preco_custo != preco_custo_anterior
            or produto.preco_venda != preco_venda_anterior
        )

        if preco_mudou and usuario_id is not None:
            HistoricoPrecoRepository.criar(
                db,
                HistoricoPreco(
                    produto_id=produto.id,
                    usuario_id=usuario_id,
                    preco_custo_anterior=preco_custo_anterior,
                    preco_custo_novo=produto.preco_custo,
                    preco_venda_anterior=preco_venda_anterior,
                    preco_venda_novo=produto.preco_venda,
                ),
            )

        produto = ProdutoRepository.atualizar(db, produto)

        # sobrescreve so' o objeto em memoria pra resposta refletir o
        # minimo DAQUELA loja -- feito DEPOIS do commit/refresh acima
        # de proposito, senao "produto.estoque_minimo = X" antes do
        # commit gravaria X no Produto.estoque_minimo GLOBAL por engano
        # (e o refresh() que vem logo depois recarregaria esse valor
        # errado do banco). Mesmo padrao ja usado em listar()/buscar().
        if novo_estoque_minimo is not None and loja_id is not None:
            produto.estoque_minimo = novo_estoque_minimo

        return produto

    @staticmethod
    def historico_precos(db: Session, produto_id: int):
        return HistoricoPrecoRepository.listar_por_produto(db, produto_id)

    @staticmethod
    def excluir(db: Session, produto_id: int):
        produto = ProdutoRepository.buscar_por_id(db, produto_id)

        if not produto:
            return False

        # Nao apaga de vez: um produto ja vendido tem itens_venda
        # apontando pra ele (produto_id NOT NULL), entao um delete de
        # verdade quebra com erro de integridade do banco. Mesmo padrao
        # ja usado em Cliente.
        produto.ativo = False
        ProdutoRepository.atualizar(db, produto)
        return True