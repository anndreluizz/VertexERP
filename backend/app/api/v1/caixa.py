from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import SessionLocal
from app.schemas.caixa import CaixaCreate, CaixaResponse
from app.services.caixa_service import CaixaService

router = APIRouter(
    prefix="/caixa",
    tags=["Caixa"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def caixa_to_response(caixa):
    if caixa is None:
        return None

    return CaixaResponse(
        id=caixa.id,
        data_abertura=caixa.data_abertura,
        data_fechamento=caixa.data_fechamento,
        saldo_inicial=caixa.saldo_inicial,
        saldo_final=caixa.saldo_final,
        status=caixa.status,
    )


@router.post("/abrir", response_model=CaixaResponse)
def abrir_caixa(
    dados: CaixaCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        caixa = CaixaService.abrir(db, dados)
        return caixa_to_response(caixa)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/fechar", response_model=CaixaResponse)
def fechar_caixa(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        caixa = CaixaService.fechar(db)
        return caixa_to_response(caixa)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/aberto", response_model=CaixaResponse | None)
def caixa_aberto(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    caixa = CaixaService.caixa_aberto(db)

    if caixa is None:
        return None

    return caixa_to_response(caixa)