from sqlalchemy.orm import Session

from app.models.caixa import Caixa


class CaixaRepository:

    @staticmethod
    def criar(db: Session, caixa: Caixa):
        db.add(caixa)
        db.commit()
        db.refresh(caixa)
        return caixa

    @staticmethod
    def buscar_aberto(
        db: Session,
        usuario_id: int,
        loja_id: int | None = None,
        para_atualizar: bool = False,
        aceitar_vencido: bool = False,
    ):
        # loja_id filtra o caixa aberto pela loja alem do usuario -- sem
        # isso, um admin com caixa aberto na Matriz nao conseguiria abrir
        # (nem operar) um caixa separado na Filial, porque o sistema
        # acharia que ele "ja tem caixa aberto" (o da outra loja)
        query = (
            db.query(Caixa)
            .filter(Caixa.status == "ABERTO")
            .filter(Caixa.usuario_id == usuario_id)
        )

        if loja_id is not None:
            query = query.filter(Caixa.loja_id == loja_id)

        # para_atualizar=True em quem vai mexer em saldo_final: trava a
        # linha ate o commit, senao duas operacoes simultaneas no mesmo
        # caixa (venda + sangria, dois terminais com o mesmo login)
        # perdiam uma das somas
        if para_atualizar:
            query = query.with_for_update()

        caixa = query.first()

        # caixa aberto ha mais de 24h nao opera (venda, sangria,
        # recebimento...): tem que fechar e abrir outro. So trava quem
        # vai mexer no saldo; fechar e ajuste de fiado passam aceitar_vencido
        if caixa and para_atualizar and not aceitar_vencido and caixa.vencido:
            raise Exception(
                "Este caixa está aberto há mais de 24 horas. Feche o caixa "
                "e abra um novo para continuar."
            )

        return caixa

    @staticmethod
    def atualizar(db: Session, caixa: Caixa):
        db.commit()
        db.refresh(caixa)
        return caixa

    @staticmethod
    def listar(db: Session, limite: int = 20, loja_id: int | None = None):
        query = db.query(Caixa)

        if loja_id is not None:
            query = query.filter(Caixa.loja_id == loja_id)

        return (
            query
            .order_by(Caixa.data_abertura.desc())
            .limit(limite)
            .all()
        )