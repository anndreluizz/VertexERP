"""Rotas PUBLICAS (sem login) da vitrine virtual -- o site da loja le'
daqui. So' GET, so' produto ativo marcado "Mostrar na vitrine", e o
schema (app/schemas/vitrine.py) e' a lista branca do que sai."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.schemas.vitrine import VitrineResponse
from app.services.vitrine_service import VitrineService

router = APIRouter(prefix="/vitrine", tags=["Vitrine"])

# catalogo muda quando alguem edita produto: cache curto. Foto nunca
# muda com o mesmo id (trocar foto = id novo), entao pode ficar 1 dia.
CACHE_CATALOGO = "public, max-age=60"
CACHE_FOTO = "public, max-age=86400"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=VitrineResponse)
def catalogo(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = CACHE_CATALOGO
    return VitrineService.catalogo(db)


@router.get("/fotos/{foto_id}")
def foto(foto_id: int, db: Session = Depends(get_db)):
    imagem = VitrineService.foto(db, foto_id)
    if imagem is None:
        raise HTTPException(status_code=404, detail="Foto não encontrada.")
    return Response(
        content=imagem, media_type="image/jpeg",
        headers={"Cache-Control": CACHE_FOTO},
    )

