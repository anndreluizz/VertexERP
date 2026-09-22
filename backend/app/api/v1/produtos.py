from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import exigir_permissao, get_current_user, resolver_loja_id
from app.database.session import SessionLocal
from app.schemas.produto import (
    ProdutoCreate,
    ProdutoUpdate,
    ProdutoResponse,
    ProdutoFotoCreate,
    ProdutoFotoResponse,
)
from app.schemas.historico_preco import HistoricoPrecoResponse
from app.schemas.kit_item import KitItemCreate, KitItemResponse
from app.schemas.produto_importacao import (
    ConfirmarImportacaoRequest,
    ConfirmarImportacaoResponse,
    ImportarCsvRequest,
    PreviewImportacaoResponse,
)
from app.services.produto_service import ProdutoService
from app.services.produto_foto_service import ProdutoFotoService
from app.services.kit_item_service import KitItemService
from app.services.importacao_produtos_service import ImportacaoProdutosService

router = APIRouter(
    prefix="/produtos",
    tags=["Produtos"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/importar-csv/preview", response_model=PreviewImportacaoResponse)
def importar_csv_preview(
    dados: ImportarCsvRequest,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    loja_efetiva = resolver_loja_id(db, usuario, loja_id)

    itens, novos, atualizados, com_erro = ImportacaoProdutosService.pre_visualizar(
        db, dados.csv_conteudo, loja_efetiva
    )

    return PreviewImportacaoResponse(
        itens=itens,
        total_novos=novos,
        total_atualizados=atualizados,
        total_com_erro=com_erro,
    )


@router.post("/importar-csv/confirmar", response_model=ConfirmarImportacaoResponse)
def importar_csv_confirmar(
    dados: ConfirmarImportacaoRequest,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    loja_efetiva = resolver_loja_id(db, usuario, loja_id)

    try:
        criados, atualizados = ImportacaoProdutosService.confirmar(
            db, dados.itens, loja_efetiva
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ConfirmarImportacaoResponse(criados=criados, atualizados=atualizados)


@router.get("/", response_model=list[ProdutoResponse])
def listar(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return ProdutoService.listar(db, skip, limit, loja_id)


@router.get("/{produto_id}", response_model=ProdutoResponse)
def buscar(
    produto_id: int,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    produto = ProdutoService.buscar(db, produto_id, loja_id)

    if not produto:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado"
        )

    return produto


@router.post("/", response_model=ProdutoResponse, status_code=201)
def criar(
    dados: ProdutoCreate,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return ProdutoService.criar(
            db, dados, resolver_loja_id(db, usuario, loja_id)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{produto_id}/foto")
def obter_foto(
    produto_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    produto = ProdutoService.buscar(db, produto_id)

    if not produto or not produto.foto:
        raise HTTPException(
            status_code=404,
            detail="Produto sem foto cadastrada."
        )

    return Response(content=produto.foto, media_type="image/jpeg")


@router.get("/{produto_id}/fotos", response_model=list[ProdutoFotoResponse])
def listar_fotos(
    produto_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return ProdutoFotoService.listar(db, produto_id)


@router.get("/{produto_id}/fotos/{foto_id}/imagem")
def obter_imagem_foto(
    produto_id: int,
    foto_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    fotos = ProdutoFotoService.listar(db, produto_id)
    foto = next((f for f in fotos if f.id == foto_id), None)

    if not foto:
        raise HTTPException(status_code=404, detail="Foto não encontrada.")

    return Response(content=foto.imagem, media_type="image/jpeg")


@router.post(
    "/{produto_id}/fotos", response_model=ProdutoFotoResponse, status_code=201
)
def adicionar_foto(
    produto_id: int,
    dados: ProdutoFotoCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return ProdutoFotoService.adicionar(db, produto_id, dados)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{produto_id}/fotos/{foto_id}")
def remover_foto(
    produto_id: int,
    foto_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return ProdutoFotoService.remover(db, produto_id, foto_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/{produto_id}/fotos/{foto_id}/principal",
    response_model=ProdutoFotoResponse,
)
def marcar_foto_principal(
    produto_id: int,
    foto_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return ProdutoFotoService.marcar_principal(db, produto_id, foto_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{produto_id}", response_model=ProdutoResponse)
def atualizar(
    produto_id: int,
    dados: ProdutoUpdate,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    produto = ProdutoService.atualizar(
        db,
        produto_id,
        dados,
        resolver_loja_id(db, usuario, loja_id),
        usuario.id,
    )

    if not produto:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado"
        )

    return produto


@router.get(
    "/{produto_id}/historico-precos",
    response_model=list[HistoricoPrecoResponse],
)
def historico_precos(
    produto_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return ProdutoService.historico_precos(db, produto_id)


@router.get(
    "/{produto_id}/variacoes",
    response_model=list[ProdutoResponse],
)
def listar_variacoes(
    produto_id: int,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return ProdutoService.listar_variacoes(
        db,
        produto_id,
        resolver_loja_id(db, usuario, loja_id),
    )


@router.delete("/{produto_id}")
def excluir(
    produto_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(exigir_permissao("produtos.excluir")),
):
    ok = ProdutoService.excluir(db, produto_id)

    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado"
        )

    return {
        "success": True,
        "message": "Produto excluído com sucesso."
    }


@router.get(
    "/{kit_id}/itens-kit",
    response_model=list[KitItemResponse],
)
def listar_itens_kit(
    kit_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return KitItemService.listar(db, kit_id)


@router.post(
    "/{kit_id}/itens-kit",
    response_model=KitItemResponse,
    status_code=201,
)
def adicionar_item_kit(
    kit_id: int,
    dados: KitItemCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return KitItemService.adicionar(db, kit_id, dados)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{kit_id}/itens-kit/{item_id}")
def remover_item_kit(
    kit_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        KitItemService.remover(db, kit_id, item_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))