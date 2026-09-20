from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin, get_current_user
from app.auth.permissoes import PERMISSOES_DISPONIVEIS
from app.database.session import SessionLocal
from app.schemas.perfil import PerfilCreate, PerfilUpdate, PerfilResponse
from app.services.perfil_service import PerfilService

router = APIRouter(
    prefix="/perfis",
    tags=["Perfis e Permissões"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/permissoes-disponiveis")
def listar_permissoes_disponiveis(
    usuario=Depends(get_current_admin),
):
    return PERMISSOES_DISPONIVEIS


@router.get("/", response_model=list[PerfilResponse])
def listar(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return PerfilService.listar(db)


@router.post("/", response_model=PerfilResponse)
def criar(
    dados: PerfilCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_admin),
):
    try:
        return PerfilService.criar(db, dados)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{perfil_id}", response_model=PerfilResponse)
def atualizar(
    perfil_id: int,
    dados: PerfilUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_admin),
):
    try:
        return PerfilService.atualizar(db, perfil_id, dados)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{perfil_id}")
def excluir(
    perfil_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_admin),
):
    try:
        PerfilService.excluir(db, perfil_id)
        return {"success": True, "message": "Perfil excluído com sucesso."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
