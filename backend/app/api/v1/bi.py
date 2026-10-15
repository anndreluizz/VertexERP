from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import exigir_permissao, loja_para_leitura
from app.database.session import SessionLocal
from app.services.bi_service import BiService
from app.services.log_auditoria_service import LogAuditoriaService

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


class DinheiroGuardado(BaseModel):
    valor: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


@router.put("/dinheiro-guardado")
def informar_dinheiro_guardado(
    dados: DinheiroGuardado,
    request: Request,
    db: Session = Depends(get_db),
    usuario=Depends(exigir_permissao("bi.ver")),
):
    """Total guardado fora dos caixas (cofre + banco) -- o sistema nao
    registra pra onde vai o dinheiro quando o caixa fecha."""
    valor, em = BiService.informar_dinheiro_guardado(db, dados.valor)
    LogAuditoriaService.registrar(
        db, usuario.id, "bi.dinheiro_guardado",
        ip=request.client.host if request.client else None,
        detalhes=f"Dinheiro guardado (cofre + banco) informado: R$ {valor}",
    )
    return {"dinheiro_guardado": valor, "dinheiro_guardado_em": em}
