from datetime import datetime

from app.schemas.base import Schema


class SolicitacaoAprovacaoResponse(Schema):
    id: int
    tipo: str
    referencia_id: int
    descricao: str
    status: str
    solicitante_id: int
    aprovador_id: int | None = None
    criado_em: datetime
    resolvido_em: datetime | None = None
