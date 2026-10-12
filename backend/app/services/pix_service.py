import re

from sqlalchemy.orm import Session

from app.models.conta_pagar import ContaPagar


def eh_copia_e_cola(pix: str | None) -> bool:
    """Pix copia e cola (BR Code) sempre começa com 000201; o resto é
    chave (CPF/CNPJ, telefone, e-mail ou aleatória)."""
    return bool(pix) and pix.strip().startswith("000201")


def _nome_base(descricao: str | None) -> str:
    # "AFEAM 3/18" e "AFEAM" são o mesmo fornecedor
    return re.sub(r"\s+\d+/\d+$", "", (descricao or "").strip()).lower()


class PixService:

    @staticmethod
    def chave_conhecida(db: Session, descricao: str | None) -> str | None:
        """Última chave Pix usada numa conta com a mesma descrição --
        conta nova do mesmo fornecedor já vem com ela. Copia e cola não
        conta: é de uma cobrança só."""

        base = _nome_base(descricao)
        if not base:
            return None

        candidatas = (
            db.query(ContaPagar.descricao, ContaPagar.pix)
            .filter(ContaPagar.pix.isnot(None), ~ContaPagar.pix.like("000201%"))
            .order_by(ContaPagar.id.desc())
            .limit(500)
        )
        for descricao_conta, pix in candidatas:
            if _nome_base(descricao_conta) == base:
                return pix
        return None

    @staticmethod
    def para_conta_nova(db: Session, pix: str | None, descricao: str | None) -> str | None:
        pix = (pix or "").strip() or None
        return pix or PixService.chave_conhecida(db, descricao)
