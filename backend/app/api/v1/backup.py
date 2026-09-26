from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_admin
from app.schemas.backup import BackupItem, BackupListResponse
from app.services.backup_service import BackupService

router = APIRouter(
    prefix="/backup",
    tags=["Backup"],
)


@router.get("/", response_model=BackupListResponse)
def listar(usuario=Depends(get_current_admin)):
    return BackupService.resumo()


@router.post("/manual", response_model=BackupItem)
def criar_manual(usuario=Depends(get_current_admin)):
    try:
        return BackupService.criar_manual()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
