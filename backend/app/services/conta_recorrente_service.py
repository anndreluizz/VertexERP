import base64
import calendar
import traceback
from datetime import date, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.enums.status_conta_pagar import StatusContaPagar
from app.models.conta_pagar import ContaPagar
from app.models.conta_recorrente import ContaRecorrente
from app.services.beneficiario_boleto_service import BeneficiarioBoletoService
from app.services.pix_service import PixService


def primeiro_dia(data: date) -> date:
    return date(data.year, data.month, 1)


def somar_meses(competencia: date, meses: int) -> date:
    """Primeiro dia do mês `meses` depois de `competencia`."""
    total = competencia.year * 12 + (competencia.month - 1) + meses
    return date(total // 12, total % 12 + 1, 1)


def vencimento_no_mes(competencia: date, dia: int) -> date:
    """Dia `dia` do mês de `competencia` -- em mês mais curto (dia 31 em
    fevereiro, por exemplo) cai no último dia do mês."""
    ultimo = calendar.monthrange(competencia.year, competencia.month)[1]
    return date(competencia.year, competencia.month, min(dia, ultimo))


class ContaRecorrenteService:

    @staticmethod
    def listar(db: Session, loja_id: int | None = None):
        query = db.query(ContaRecorrente).filter(ContaRecorrente.ativa.is_(True))
        if loja_id is not None:
            query = query.filter(ContaRecorrente.loja_id == loja_id)
        return query.order_by(ContaRecorrente.dia_vencimento, ContaRecorrente.id).all()

    @staticmethod
    def criar(db: Session, dados, loja_id: int | None = None):
        """Cadastra a conta fixa e já cria a conta do primeiro mês, com o
        vencimento informado."""

        recorrente = ContaRecorrente(
            descricao=dados.descricao.strip(),
            valor=dados.valor,
            dia_vencimento=dados.primeiro_vencimento.day,
            valor_variavel=dados.valor_variavel,
            categoria=dados.categoria,
            centro_custo=dados.centro_custo,
            plano_conta_id=dados.plano_conta_id,
            observacao=dados.observacao,
            loja_id=loja_id,
            ativa=True,
        )
        db.add(recorrente)
        db.flush()

        competencia = primeiro_dia(dados.primeiro_vencimento)
        if getattr(dados, "meses", None):
            recorrente.fim_competencia = somar_meses(competencia, dados.meses - 1)
        conta = ContaRecorrenteService._criar_conta_do_mes(
            db, recorrente, competencia, dados.valor, a_confirmar=False
        )
        conta.numero_boleto = getattr(dados, "numero_boleto", None)
        conta.pix = PixService.para_conta_nova(
            db, getattr(dados, "pix", None), recorrente.descricao
        )
        if getattr(dados, "documento_base64", None):
            conta.documento = base64.b64decode(dados.documento_base64)
            conta.documento_nome = dados.documento_nome
            conta.documento_tipo = dados.documento_tipo
        recorrente.ultima_competencia = competencia

        db.commit()
        db.refresh(recorrente)

        BeneficiarioBoletoService.aprender(
            db, conta.numero_boleto, conta.descricao, conta.categoria,
            getattr(dados, "beneficiario_cnpj", None),
        )

        # o primeiro vencimento pode ser de um mês que já passou
        ContaRecorrenteService.gerar_pendentes(db)

        return recorrente

    @staticmethod
    def atualizar(db: Session, recorrente_id: int, dados):
        """Muda os próximos meses. As contas já criadas ficam como
        estão (corrige-se cada uma em Contas a Pagar)."""

        recorrente = db.query(ContaRecorrente).filter(
            ContaRecorrente.id == recorrente_id
        ).first()

        if recorrente is None:
            return None

        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(recorrente, campo, valor.strip() if campo == "descricao" else valor)

        db.commit()
        db.refresh(recorrente)
        return recorrente

    @staticmethod
    def parar(db: Session, recorrente_id: int):
        """Para de repetir: nenhum mês novo é criado. As contas já
        criadas continuam em Contas a Pagar."""

        recorrente = db.query(ContaRecorrente).filter(
            ContaRecorrente.id == recorrente_id
        ).first()

        if recorrente is None:
            return False

        recorrente.ativa = False
        db.commit()
        return True

    @staticmethod
    def _criar_conta_do_mes(db, recorrente, competencia, valor, a_confirmar):
        vencimento = vencimento_no_mes(competencia, recorrente.dia_vencimento)
        conta = ContaPagar(
            data_emissao=datetime.now(),
            data_vencimento=datetime(vencimento.year, vencimento.month, vencimento.day),
            valor=valor,
            descricao=recorrente.descricao,
            categoria=recorrente.categoria,
            centro_custo=recorrente.centro_custo,
            plano_conta_id=recorrente.plano_conta_id,
            observacao=recorrente.observacao,
            status=StatusContaPagar.PENDENTE.value,
            loja_id=recorrente.loja_id,
            recorrente_id=recorrente.id,
            competencia=competencia,
            valor_a_confirmar=a_confirmar,
            # mes novo: a chave Pix do fornecedor (copia e cola nao, ver
            # PixService.chave_conhecida)
            pix=PixService.chave_conhecida(db, recorrente.descricao),
        )
        db.add(conta)
        return conta

    @staticmethod
    def gerar_pendentes(db: Session, hoje: date | None = None) -> int:
        """Cria a conta de cada mês que virou desde a última vez, até o
        mês atual. Roda quando alguém abre Contas a Pagar (não precisa de
        agendador); chamar de novo no mesmo mês não cria nada. Nunca
        levanta erro: listar contas não pode quebrar por causa disso."""

        mes_atual = primeiro_dia(hoje or date.today())
        criadas = 0

        try:
            recorrentes = db.query(ContaRecorrente).filter(
                ContaRecorrente.ativa.is_(True)
            ).all()

            for recorrente in recorrentes:

                proxima = (
                    somar_meses(recorrente.ultima_competencia, 1)
                    if recorrente.ultima_competencia else mes_atual
                )

                limite = mes_atual
                if recorrente.fim_competencia and recorrente.fim_competencia < limite:
                    limite = recorrente.fim_competencia

                while proxima <= limite:

                    # luz: recorrente.valor e a estimativa -- acompanha o
                    # ultimo valor corrigido (ContaPagarService.atualizar)
                    # e o "Mudar valor" das Contas fixas
                    ContaRecorrenteService._criar_conta_do_mes(
                        db, recorrente, proxima, recorrente.valor,
                        a_confirmar=recorrente.valor_variavel,
                    )
                    recorrente.ultima_competencia = proxima
                    db.flush()
                    criadas += 1
                    proxima = somar_meses(proxima, 1)

                # chegou no ultimo mes do prazo: nao tem mais o que criar
                if (
                    recorrente.fim_competencia
                    and recorrente.ultima_competencia
                    and recorrente.ultima_competencia >= recorrente.fim_competencia
                ):
                    recorrente.ativa = False

            db.commit()

        except IntegrityError:
            # outro terminal gerou o mesmo mês ao mesmo tempo -- o dele vale
            db.rollback()
        except Exception:
            traceback.print_exc()
            db.rollback()

        return criadas
