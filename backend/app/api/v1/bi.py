from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import exigir_permissao, loja_para_leitura
from app.database.session import SessionLocal
from app.services.bi_service import BiService

router = APIRouter(
    prefix="/bi",
    tags=["Inteligência de Negócios"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/resumo")
def resumo(
    data_inicio: date = Query(...),
    data_fim: date = Query(...),
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(exigir_permissao("bi.ver")),
):
    try:
        return BiService.resumo(
            db, data_inicio, data_fim, loja_para_leitura(usuario, loja_id)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
