import re
import traceback

from sqlalchemy.orm import Session

from app.models.beneficiario_boleto import BeneficiarioBoleto
from app.models.conta_pagar import ContaPagar
from app.services import boleto_service

# " 2/3" no fim da descricao de uma parcela -- o fornecedor e' o resto
_SUFIXO_PARCELA = re.compile(r"\s+\d+/\d+$")


def _so_digitos(texto):
    return re.sub(r"\D", "", texto or "")


class BeneficiarioBoletoService:

    @staticmethod
    def buscar(db: Session, *chaves):
        for chave in chaves:
            if not chave:
                continue
            achado = db.query(BeneficiarioBoleto).filter(
                BeneficiarioBoleto.chave == chave
            ).first()
            if achado:
                return achado
        return None

    @staticmethod
    def aprender(db: Session, numero_boleto, descricao, categoria, cnpj=None):
        """Guarda nome/categoria do fornecedor pela chave do boleto (e
        pelo CNPJ, se veio do PDF). Nunca levanta erro -- salvar a conta
        e' o que importa; aprender e' bonus."""

        try:
            chaves = []
            if numero_boleto:
                try:
                    lido = boleto_service.ler_codigo(numero_boleto)
                    chaves.append(lido["chave_beneficiario"])
                except boleto_service.BoletoInvalidoError:
                    pass
            if cnpj and len(_so_digitos(cnpj)) == 14:
                chaves.append(f"cnpj:{_so_digitos(cnpj)}")

            nome = _SUFIXO_PARCELA.sub("", (descricao or "").strip())
            if not nome:
                return

            for chave in filter(None, chaves):
                registro = db.query(BeneficiarioBoleto).filter(
                    BeneficiarioBoleto.chave == chave
                ).first()
                if registro is None:
                    registro = BeneficiarioBoleto(chave=chave, nome=nome[:120])
                    db.add(registro)
                registro.nome = nome[:120]
                if categoria:
                    registro.categoria = categoria
            db.commit()
        except Exception:
            traceback.print_exc()
            db.rollback()

    @staticmethod
    def ler(db: Session, codigo=None, pdf=None):
        """Lê o boleto e completa com o que o sistema já sabe: nome e
        categoria aprendidos, e se esse boleto já foi lançado."""

        if pdf is not None:
            resultado = boleto_service.ler_pdf(pdf)
        elif codigo:
            resultado = boleto_service.ler_codigo(codigo)
            resultado["beneficiario_nome"] = None
            resultado["beneficiario_cnpj"] = None
        else:
            raise boleto_service.BoletoInvalidoError("Informe o código ou o PDF do boleto.")

        cnpj = resultado.get("beneficiario_cnpj")
        conhecido = BeneficiarioBoletoService.buscar(
            db,
            resultado.get("chave_beneficiario"),
            f"cnpj:{cnpj}" if cnpj else None,
        )

        resultado["fornecedor_sugerido"] = (
            conhecido.nome if conhecido else resultado.get("beneficiario_nome")
        )
        if conhecido and conhecido.categoria:
            resultado["categoria_sugerida"] = conhecido.categoria

        resultado["ja_lancado"] = None
        barras = resultado.get("codigo_barras")
        if barras:
            for conta in db.query(ContaPagar).filter(
                ContaPagar.numero_boleto.isnot(None),
                ContaPagar.status != "CANCELADO",
            ).all():
                digitos = _so_digitos(conta.numero_boleto)
                if not digitos:
                    continue
                try:
                    if digitos == barras or (
                        len(digitos) in (47, 48)
                        and boleto_service.ler_codigo(digitos)["codigo_barras"] == barras
                    ):
                        resultado["ja_lancado"] = {
                            "id": conta.id,
                            "descricao": conta.descricao,
                            "status": conta.status,
                            "valor": conta.valor,
                        }
                        break
                except boleto_service.BoletoInvalidoError:
                    continue

        resultado["parcela_sugerida"] = None
        if resultado["ja_lancado"] is None:
            parcela = BeneficiarioBoletoService.achar_parcela(db, resultado)
            if parcela is not None:
                resultado["parcela_sugerida"] = {
                    "id": parcela.id,
                    "descricao": parcela.descricao,
                    "parcela_numero": parcela.parcela_numero,
                    "parcela_total": parcela.parcela_total,
                    "valor": parcela.valor,
                    "data_vencimento": parcela.data_vencimento,
                }

        return resultado

    @staticmethod
    def achar_parcela(db: Session, lido, folga_dias=10):
        """Parcela em aberto, ainda sem codigo, que esse boleto paga:
        mesmo valor e vencimento perto (o dia muda de mes pra mes, ex.
        AFEAM 24/26). Empate: o nome do fornecedor decide, depois a data
        mais perto."""

        valor, vencimento = lido.get("valor"), lido.get("vencimento")
        if not valor or not vencimento:
            return None

        candidatas = [
            conta for conta in db.query(ContaPagar).filter(
                ContaPagar.parcelamento_id.isnot(None),
                ContaPagar.status == "PENDENTE",
                ContaPagar.valor == valor,
            ).all()
            if not _so_digitos(conta.numero_boleto)
            and abs((conta.data_vencimento.date() - vencimento).days) <= folga_dias
        ]
        if not candidatas:
            return None

        nome = (lido.get("fornecedor_sugerido") or "").strip().upper()

        def ordem(conta):
            fornecedor = _SUFIXO_PARCELA.sub("", (conta.descricao or "").strip()).upper()
            return (
                not nome or fornecedor != nome,
                abs((conta.data_vencimento.date() - vencimento).days),
                conta.parcela_numero or 0,
            )

        return min(candidatas, key=ordem)
