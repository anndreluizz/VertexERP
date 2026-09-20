from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, resolver_loja_id
from app.database.session import SessionLocal
from app.schemas.movimento_estoque import (
    MovimentoEstoqueCreate,
    MovimentoEstoqueResponse,
)
from app.schemas.transferencia_estoque import (
    TransferenciaEstoqueCreate,
    TransferenciaEstoqueResponse,
)
from app.schemas.contagem_estoque import (
    ContagemEstoqueCreate,
    ContagemEstoqueResponse,
    ItemContagemEstoqueResponse,
    ItemContagemEstoqueUpdate,
)
from app.services.movimento_estoque_service import MovimentoEstoqueService
from app.services.transferencia_estoque_service import (
    TransferenciaEstoqueService,
)
from app.services.contagem_estoque_service import ContagemEstoqueService

router = APIRouter(
    prefix="/estoque",
    tags=["Estoque"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post(
    "/movimentos",
    response_model=MovimentoEstoqueResponse,
    status_code=201,
)
def criar_movimento(
    dados: MovimentoEstoqueCreate,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        movimento = MovimentoEstoqueService.criar(
            db,
            dados,
            usuario.id,
            resolver_loja_id(db, usuario, loja_id),
        )

        return MovimentoEstoqueResponse.from_orm(movimento)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/movimentos", response_model=list[MovimentoEstoqueResponse])
def listar_movimentos(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    movimentos = MovimentoEstoqueService.listar(db)

    return [
        MovimentoEstoqueResponse.from_orm(m)
        for m in movimentos
    ]


@router.post(
    "/transferencias",
    response_model=TransferenciaEstoqueResponse,
    status_code=201,
)
def criar_transferencia(
    dados: TransferenciaEstoqueCreate,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        transferencia = TransferenciaEstoqueService.criar(
            db,
            dados,
            usuario.id,
            resolver_loja_id(db, usuario, loja_id),
        )

        return TransferenciaEstoqueResponse.from_orm(transferencia)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/transferencias", response_model=list[TransferenciaEstoqueResponse]
)
def listar_transferencias(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    transferencias = TransferenciaEstoqueService.listar(db, skip, limit)

    return [
        TransferenciaEstoqueResponse.from_orm(t)
        for t in transferencias
    ]


@router.get(
    "/movimentos/produto/{produto_id}",
    response_model=list[MovimentoEstoqueResponse],
)
def listar_por_produto(
    produto_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    movimentos = MovimentoEstoqueService.listar_por_produto(
        db,
        produto_id,
    )

    return [
        MovimentoEstoqueResponse.from_orm(m)
        for m in movimentos
    ]


@router.post(
    "/contagens",
    response_model=ContagemEstoqueResponse,
    status_code=201,
)
def abrir_contagem(
    dados: ContagemEstoqueCreate,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        contagem = ContagemEstoqueService.abrir(
            db,
            dados,
            usuario.id,
            resolver_loja_id(db, usuario, loja_id),
        )

        return ContagemEstoqueResponse.from_orm(contagem)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/contagens/aberta", response_model=ContagemEstoqueResponse | None)
def contagem_aberta(
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    contagem = ContagemEstoqueService.buscar_aberta(
        db, resolver_loja_id(db, usuario, loja_id)
    )

    if contagem is None:
        return None

    return ContagemEstoqueResponse.from_orm(contagem)


@router.get("/contagens", response_model=list[ContagemEstoqueResponse])
def listar_contagens(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    contagens = ContagemEstoqueService.listar(db, skip, limit)

    return [ContagemEstoqueResponse.from_orm(c) for c in contagens]


@router.get("/contagens/{contagem_id}", response_model=ContagemEstoqueResponse)
def obter_contagem(
    contagem_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        contagem = ContagemEstoqueService.buscar_por_id(db, contagem_id)
        return ContagemEstoqueResponse.from_orm(contagem)

    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put(
    "/contagens/{contagem_id}/itens/{item_id}",
    response_model=ItemContagemEstoqueResponse,
)
def registrar_item_contagem(
    contagem_id: int,
    item_id: int,
    dados: ItemContagemEstoqueUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        item = ContagemEstoqueService.registrar_item(
            db, contagem_id, item_id, dados.quantidade_contada
        )
        return ItemContagemEstoqueResponse.from_orm(item)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/contagens/{contagem_id}/finalizar",
    response_model=ContagemEstoqueResponse,
)
def finalizar_contagem(
    contagem_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        contagem = ContagemEstoqueService.finalizar(
            db, contagem_id, usuario.id
        )
        return ContagemEstoqueResponse.from_orm(contagem)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/contagens/{contagem_id}/cancelar",
    response_model=ContagemEstoqueResponse,
)
def cancelar_contagem(
    contagem_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        contagem = ContagemEstoqueService.cancelar(db, contagem_id)
        return ContagemEstoqueResponse.from_orm(contagem)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
