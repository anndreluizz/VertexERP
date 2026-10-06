from decimal import Decimal

from sqlalchemy.orm import Session

from app.enums.forma_pagamento import FormaPagamento
from app.repositories.produto_repository import ProdutoRepository
from app.schemas.produto import ProdutoCreate
from app.schemas.compra import CompraCreate, ItemCompraCreate
from app.schemas.fornecedor import FornecedorCreate
from app.schemas.nfe_importacao import (
    FornecedorPreviewResponse,
    ImportarNFeConfirmarRequest,
    ItemPreviewResponse,
    NFeImportarRequest,
    NFePreviewResponse,
)
from app.services.compra_service import CompraService
from app.services.fornecedor_service import FornecedorService
from app.services.nfe_service import parsear_nfe
from app.services.produto_service import ProdutoService


def _preco_sugerido(custo: Decimal, margem: Decimal) -> Decimal:
    return (custo * (1 + margem / 100)).quantize(Decimal("0.01"))


class ImportacaoNfeService:

    @staticmethod
    def pre_visualizar(
        db: Session, dados: NFeImportarRequest, loja_id: int | None = None
    ) -> NFePreviewResponse:
        """So' leitura -- nenhum db.add/db.commit aqui."""

        extraida = parsear_nfe(dados.xml_conteudo)

        fornecedor = FornecedorService.buscar_por_cnpj(
            db, extraida.fornecedor.cnpj
        )

        margem = fornecedor.margem_padrao if fornecedor else Decimal("0")

        fornecedor_preview = FornecedorPreviewResponse(
            encontrado=fornecedor is not None,
            id=fornecedor.id if fornecedor else None,
            cnpj=extraida.fornecedor.cnpj,
            razao_social=(
                fornecedor.razao_social
                if fornecedor
                else extraida.fornecedor.razao_social
            ),
            nome_fantasia=(
                fornecedor.nome_fantasia
                if fornecedor
                else extraida.fornecedor.nome_fantasia
            ),
            margem_padrao=margem,
        )

        itens_preview = []

        for item in extraida.itens:

            produto = ProdutoRepository.buscar_por_codigo(
                db, item.codigo, loja_id
            )

            itens_preview.append(
                ItemPreviewResponse(
                    codigo=item.codigo,
                    descricao=item.descricao,
                    codigo_barras=item.codigo_barras,
                    quantidade=item.quantidade,
                    custo=item.valor_unitario,
                    produto_id=produto.id if produto else None,
                    preco_atual=produto.preco_venda if produto else None,
                    preco_sugerido=_preco_sugerido(
                        item.valor_unitario, margem
                    ),
                )
            )

        return NFePreviewResponse(
            fornecedor=fornecedor_preview,
            itens=itens_preview,
        )

    @staticmethod
    def confirmar(
        db: Session,
        dados: ImportarNFeConfirmarRequest,
        usuario_id: int,
        loja_id: int | None = None,
    ):
        """Transacional: fornecedor + produtos novos/atualizados + compra
        + itens + (se PRAZO) conta a pagar. Qualquer erro no meio -> sobe
        a excecao (o handler global vira 400); CompraService.criar/
        MovimentoEstoqueService.criar ja fazem seus proprios commits
        pontuais, mesmo padrao usado no resto do backend -- nao ha rollback
        magico de tudo, mas nenhum passo aqui e' silenciosamente ignorado."""

        if dados.fornecedor_id is not None:
            fornecedor = FornecedorService.buscar(db, dados.fornecedor_id)
        elif dados.fornecedor_novo is not None:
            fornecedor = FornecedorService.criar(
                db,
                FornecedorCreate(
                    razao_social=dados.fornecedor_novo.razao_social,
                    nome_fantasia=dados.fornecedor_novo.nome_fantasia,
                    cnpj=dados.fornecedor_novo.cnpj,
                    margem_padrao=dados.fornecedor_novo.margem_padrao,
                ),
            )
        else:
            raise Exception(
                "Informe um fornecedor existente ou os dados de um novo."
            )

        itens_compra = []

        for item in dados.itens:

            produto_id = item.produto_id

            if produto_id is None:
                # estoque=0 de proposito: a entrada de verdade (com
                # historico em MovimentoEstoque) acontece uniformemente
                # pra TODO item -- novo ou existente -- dentro de
                # CompraService.criar logo abaixo. Se semeasse estoque
                # aqui E deixasse o CompraService.criar dar entrada de
                # novo, o produto novo ficaria com o dobro da quantidade
                # comprada.
                produto = ProdutoService.criar(
                    db,
                    ProdutoCreate(
                        codigo=item.codigo,
                        codigo_barras=item.codigo_barras,
                        nome=item.descricao,
                        categoria=None,
                        preco_custo=item.custo,
                        preco_venda=item.preco_venda,
                        estoque=0,
                        estoque_minimo=0,
                    ),
                    loja_id,
                )
                produto_id = produto.id
            else:
                produto = ProdutoRepository.buscar_por_id(db, produto_id)

                if not produto:
                    raise Exception(
                        f"Produto {produto_id} não encontrado."
                    )

                produto.preco_custo = item.custo
                if item.atualizar_preco_venda:
                    produto.preco_venda = item.preco_venda
                ProdutoRepository.atualizar(db, produto)

            itens_compra.append(
                ItemCompraCreate(
                    produto_id=produto_id,
                    quantidade=item.quantidade,
                    valor_unitario=item.custo,
                )
            )

        compra = CompraService.criar(
            db,
            CompraCreate(
                fornecedor_id=fornecedor.id,
                observacao=dados.observacao,
                forma_pagamento=dados.forma_pagamento,
                data_vencimento=dados.data_vencimento,
                numero_parcelas=dados.numero_parcelas,
                itens=itens_compra,
            ),
            usuario_id,
            loja_id,
            fornecedor.razao_social,
        )

        return compra
