import base64
import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.enums.status_conta_pagar import StatusContaPagar
from app.services.beneficiario_boleto_service import BeneficiarioBoletoService
from app.services.conta_recorrente_service import (
    ContaRecorrenteService,
    primeiro_dia,
    somar_meses,
    vencimento_no_mes,
)

from app.models.conta_pagar import ContaPagar
from app.models.conta_recorrente import ContaRecorrente

from app.repositories.conta_pagar_repository import (
    ContaPagarRepository,
)

from app.schemas.conta_pagar import (
    ContaPagarCreate,
    ContaPagarUpdate,
)

from app.services.conta_pagar_evento_service import ContaPagarEventoService
from app.services.notificacao_service import NotificacaoService
from app.services.pix_service import PixService, eh_copia_e_cola

# rotulos legiveis pra montar o "detalhes" dos eventos de auditoria --
# mesmos valores usados em Venda.forma_pagamento.
_NOMES_FORMA_PAGAMENTO = {
    "PIX": "Pix",
    "TRANSFERENCIA": "Transferência",
    "DINHEIRO": "Dinheiro",
    "CARTAO": "Cartão",
    "BOLETO": "Boleto",
}


def _moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "_").replace(".", ",").replace(
        "_", "."
    )


class ContaPagarService:

    @staticmethod
    def criar(
        db: Session,
        dados: ContaPagarCreate,
        usuario_id: int | None = None,
        dispositivo: str | None = None,
        loja_id: int | None = None,
    ):

        conta = ContaPagar(
            data_emissao=datetime.now(),
            data_vencimento=dados.data_vencimento,
            data_pagamento=None,
            valor=dados.valor,
            descricao=dados.descricao,
            categoria=dados.categoria,
            centro_custo=dados.centro_custo,
            plano_conta_id=dados.plano_conta_id,
            observacao=dados.observacao,
            numero_boleto=dados.numero_boleto,
            pix=PixService.para_conta_nova(db, dados.pix, dados.descricao),
            status=StatusContaPagar.PENDENTE.value,
            loja_id=loja_id,
        )

        if dados.documento_base64:
            conta.documento = base64.b64decode(dados.documento_base64)
            conta.documento_nome = dados.documento_nome
            conta.documento_tipo = dados.documento_tipo

        conta = ContaPagarRepository.criar(
            db,
            conta,
        )

        ContaPagarEventoService.registrar(
            db, conta.id, "CRIADA",
            usuario_id=usuario_id, dispositivo=dispositivo,
        )

        BeneficiarioBoletoService.aprender(
            db, conta.numero_boleto, conta.descricao, conta.categoria,
            getattr(dados, "beneficiario_cnpj", None),
        )

        if dados.documento_base64:
            ContaPagarEventoService.registrar(
                db, conta.id, "DOCUMENTO_ANEXADO",
                usuario_id=usuario_id, dispositivo=dispositivo,
            )
            NotificacaoService.enviar_para_admins(
                db,
                "Novo boleto cadastrado",
                f"{conta.descricao or 'Despesa'} — {_moeda(conta.valor)}",
                excluir_usuario_id=usuario_id,
            )
        else:
            NotificacaoService.enviar_para_admins(
                db,
                "Nova despesa",
                f"{conta.descricao or 'Despesa'} — {_moeda(conta.valor)}",
                excluir_usuario_id=usuario_id,
            )

        return conta

    @staticmethod
    def criar_parcelado(
        db: Session,
        dados,
        usuario_id: int | None = None,
        loja_id: int | None = None,
    ):
        """Boleto parcelado: cria N contas de dados.valor cada (valor da
        parcela), a primeira no vencimento informado e as outras no
        mesmo dia dos meses seguintes. Descricao ganha " 1/N", " 2/N"...
        O documento anexado (se houver) fica so' na primeira."""

        descricao = (dados.descricao or "Despesa").strip()
        n = dados.numero_parcelas

        if len(descricao) + len(f" {n}/{n}") > 120:
            raise Exception("Descrição muito longa para parcelar.")

        primeiro = dados.data_vencimento.date()
        competencia = primeiro_dia(primeiro)

        if dados.vencimentos:
            if len(dados.vencimentos) != n:
                raise Exception("Informe uma data para cada parcela.")
            vencimentos = list(dados.vencimentos)
        elif dados.intervalo == "30_DIAS":
            vencimentos = [primeiro + timedelta(days=30 * i) for i in range(n)]
        else:
            vencimentos = [
                vencimento_no_mes(somar_meses(competencia, i), primeiro.day)
                for i in range(n)
            ]

        parcelamento_id = uuid.uuid4().hex
        contas = []

        # copia e cola e de uma cobranca so' (fica na 1a parcela, como o
        # boleto); chave Pix vale pra todas
        pix = PixService.para_conta_nova(db, dados.pix, descricao)
        pix_demais = None if eh_copia_e_cola(pix) else pix
        if pix_demais is None:
            pix_demais = PixService.chave_conhecida(db, descricao)

        for indice in range(n):

            vencimento = vencimentos[indice]

            conta = ContaPagar(
                data_emissao=datetime.now(),
                data_vencimento=datetime(vencimento.year, vencimento.month, vencimento.day),
                valor=dados.valor,
                descricao=f"{descricao} {indice + 1}/{n}",
                categoria=dados.categoria,
                centro_custo=dados.centro_custo,
                plano_conta_id=dados.plano_conta_id,
                observacao=dados.observacao,
                numero_boleto=dados.numero_boleto if indice == 0 else None,
                pix=pix if indice == 0 else pix_demais,
                status=StatusContaPagar.PENDENTE.value,
                loja_id=loja_id,
                parcelamento_id=parcelamento_id,
                parcela_numero=indice + 1,
                parcela_total=n,
            )

            if indice == 0 and dados.documento_base64:
                conta.documento = base64.b64decode(dados.documento_base64)
                conta.documento_nome = dados.documento_nome
                conta.documento_tipo = dados.documento_tipo

            db.add(conta)
            contas.append(conta)

        db.commit()

        for conta in contas:
            db.refresh(conta)
            ContaPagarEventoService.registrar(
                db, conta.id, "CRIADA", usuario_id=usuario_id,
            )

        BeneficiarioBoletoService.aprender(
            db, dados.numero_boleto, descricao, dados.categoria,
            getattr(dados, "beneficiario_cnpj", None),
        )

        NotificacaoService.enviar_para_admins(
            db,
            "Nova despesa parcelada",
            f"{descricao} — {n}x de {_moeda(dados.valor)}",
            excluir_usuario_id=usuario_id,
        )

        return contas

    @staticmethod
    def listar_parcelamento(db: Session, parcelamento_id: str):
        return (
            db.query(ContaPagar)
            .filter(ContaPagar.parcelamento_id == parcelamento_id)
            .order_by(ContaPagar.parcela_numero, ContaPagar.data_vencimento)
            .all()
        )

    @staticmethod
    def cancelar_parcelas_restantes(
        db: Session, parcelamento_id: str, usuario_id: int | None = None
    ):
        """Cancela as parcelas ainda pendentes (acordo com o fornecedor,
        compra devolvida...). As pagas ficam como estao."""

        pendentes = [
            c for c in ContaPagarService.listar_parcelamento(db, parcelamento_id)
            if c.status == StatusContaPagar.PENDENTE.value
        ]

        if not pendentes:
            raise Exception("Não há parcelas pendentes nesse parcelamento.")

        for conta in pendentes:
            conta.status = StatusContaPagar.CANCELADO.value
        db.commit()

        for conta in pendentes:
            ContaPagarEventoService.registrar(
                db, conta.id, "CANCELADA", usuario_id=usuario_id,
                detalhes="Parcelas restantes canceladas",
            )

        return len(pendentes)

    @staticmethod
    def criar_compra_prazo(
        db: Session,
        compra,
        usuario_id: int | None = None,
        loja_id: int | None = None,
        numero_parcelas: int = 1,
    ):
        """Gera automaticamente a(s) conta(s) a pagar de uma Compra feita
        a prazo (ver CompraService.criar) -- sem isso, uma compra PRAZO
        ficaria sem nenhum rastro em Contas a Pagar. numero_parcelas > 1
        divide compra.valor_total em N contas iguais (o resto de
        arredondamento fica na ULTIMA parcela, nao na primeira -- evita
        centavo sumindo/sobrando sem explicacao), uma a cada 30 dias a
        partir de compra.data_vencimento."""

        if compra.fornecedor_id is None:
            raise Exception(
                "Compra a prazo exige um fornecedor."
            )

        if compra.data_vencimento is None:
            raise Exception(
                "Informe a data de vencimento."
            )

        if numero_parcelas < 1:
            raise Exception(
                "O número de parcelas precisa ser pelo menos 1."
            )

        valor_parcela = round(compra.valor_total / numero_parcelas, 2)
        valor_ultima_parcela = compra.valor_total - (
            valor_parcela * (numero_parcelas - 1)
        )

        contas = []

        for indice in range(numero_parcelas):

            valor = (
                valor_ultima_parcela
                if indice == numero_parcelas - 1
                else valor_parcela
            )

            descricao = f"Compra #{compra.id}"
            if numero_parcelas > 1:
                descricao += f" - Parcela {indice + 1}/{numero_parcelas}"

            conta = ContaPagar(
                fornecedor_id=compra.fornecedor_id,
                compra_id=compra.id,
                data_emissao=datetime.now(),
                data_vencimento=compra.data_vencimento
                + timedelta(days=30 * indice),
                data_pagamento=None,
                valor=valor,
                descricao=descricao,
                categoria="Compra de mercadoria",
                observacao="Gerada automaticamente pela compra.",
                status=StatusContaPagar.PENDENTE.value,
                loja_id=loja_id,
            )

            conta = ContaPagarRepository.criar(
                db,
                conta,
            )

            ContaPagarEventoService.registrar(
                db, conta.id, "CRIADA",
                usuario_id=usuario_id,
            )

            contas.append(conta)

        return contas

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100, loja_id: int | None = None):
        # so na 1a pagina: criar contas no meio da varredura desloca o offset
        if skip == 0:
            ContaRecorrenteService.gerar_pendentes(db)
        return ContaPagarRepository.listar(db, skip, limit, loja_id)

    @staticmethod
    def listar_pendentes(db: Session, loja_id: int | None = None):
        ContaRecorrenteService.gerar_pendentes(db)
        return ContaPagarRepository.listar_pendentes(db, loja_id)

    @staticmethod
    def listar_pagas(db: Session, skip: int = 0, limit: int = 100):
        return ContaPagarRepository.listar_pagas(db, skip, limit)

    @staticmethod
    def buscar_por_id(
        db: Session,
        conta_id: int,
    ):
        return ContaPagarRepository.buscar_por_id(
            db,
            conta_id,
        )

    @staticmethod
    def atualizar(
        db: Session,
        conta_id: int,
        dados: ContaPagarUpdate,
        usuario_id: int | None = None,
        dispositivo: str | None = None,
    ):

        conta = ContaPagarRepository.buscar_por_id(
            db,
            conta_id,
        )

        if not conta:
            raise Exception("Conta não encontrada.")

        dados_dict = dados.model_dump(
            exclude_unset=True,
            exclude={
                "documento_base64",
                "documento_nome",
                "documento_tipo",
            },
        )

        # a tela de edicao sempre manda o valor: so conta como correcao
        # (e confirma a luz) se ele mudou de fato
        valor_mudou = (
            dados_dict.get("valor") is not None
            and dados_dict["valor"] != conta.valor
        )

        for campo, valor in dados_dict.items():
            setattr(conta, campo, valor)

        if valor_mudou:
            conta.valor_a_confirmar = False
            # o valor corrigido vira a estimativa dos proximos meses
            recorrente = (
                db.get(ContaRecorrente, conta.recorrente_id)
                if conta.recorrente_id else None
            )
            if recorrente is not None and recorrente.valor_variavel:
                recorrente.valor = conta.valor

        dados_dict.pop("beneficiario_cnpj", None)

        # so troca o documento se vier um novo -- editar outros campos
        # da despesa nao pode apagar o boleto ja anexado sem querer.
        if dados.documento_base64:
            conta.documento = base64.b64decode(dados.documento_base64)
            conta.documento_nome = dados.documento_nome
            conta.documento_tipo = dados.documento_tipo

        conta = ContaPagarRepository.atualizar(
            db,
            conta,
        )

        if "numero_boleto" in dados_dict or "descricao" in dados_dict:
            BeneficiarioBoletoService.aprender(
                db, conta.numero_boleto, conta.descricao, conta.categoria,
            )

        if dados.documento_base64:
            ContaPagarEventoService.registrar(
                db, conta.id, "DOCUMENTO_ANEXADO",
                usuario_id=usuario_id, dispositivo=dispositivo,
            )
            NotificacaoService.enviar_para_admins(
                db,
                "Novo boleto cadastrado",
                f"{conta.descricao or 'Despesa'} — {_moeda(conta.valor)}",
                excluir_usuario_id=usuario_id,
            )

        return conta

    @staticmethod
    def remover_documento(
        db: Session,
        conta_id: int,
    ):

        conta = ContaPagarRepository.buscar_por_id(
            db,
            conta_id,
        )

        if not conta:
            raise Exception("Conta não encontrada.")

        conta.documento = None
        conta.documento_nome = None
        conta.documento_tipo = None

        return ContaPagarRepository.atualizar(
            db,
            conta,
        )

    @staticmethod
    def pagar(
        db: Session,
        conta_id: int,
        forma_pagamento: str | None = None,
        banco_pagamento: str | None = None,
        numero_transacao: str | None = None,
        comprovante_base64: str | None = None,
        comprovante_nome: str | None = None,
        comprovante_tipo: str | None = None,
        usuario_id: int | None = None,
        dispositivo: str | None = None,
    ):
        # Conta paga NAO mexe no caixa do dia, nem em dinheiro: a loja
        # paga boleto com o dinheiro guardado (o total de todos os
        # caixas), nao com a gaveta do turno. Ela ja sai do total geral
        # em CaixaService.entradas (sobrou = entrou - contas pagas -
        # sangrias). Antes saia da gaveta e a loja lancava um suprimento
        # do mesmo valor so pra conta do dia fechar.

        conta = ContaPagarRepository.buscar_por_id(
            db,
            conta_id,
        )

        if not conta:
            raise Exception("Conta não encontrada.")

        if conta.status == StatusContaPagar.PAGO.value:
            raise Exception("Conta já foi paga.")

        if conta.status == StatusContaPagar.CANCELADO.value:
            raise Exception("Conta cancelada.")

        conta.status = StatusContaPagar.PAGO.value
        conta.data_pagamento = datetime.now()
        conta.valor_a_confirmar = False
        conta.forma_pagamento = forma_pagamento
        conta.banco_pagamento = banco_pagamento
        conta.numero_transacao = numero_transacao

        if comprovante_base64:
            conta.comprovante_pagamento = base64.b64decode(
                comprovante_base64
            )
            conta.comprovante_pagamento_nome = comprovante_nome
            conta.comprovante_pagamento_tipo = comprovante_tipo

        conta = ContaPagarRepository.atualizar(
            db,
            conta,
        )

        detalhes = None
        if forma_pagamento:
            detalhes = f"Pago via {_NOMES_FORMA_PAGAMENTO.get(forma_pagamento, forma_pagamento)}."

        ContaPagarEventoService.registrar(
            db, conta.id, "PAGA",
            usuario_id=usuario_id, dispositivo=dispositivo,
            detalhes=detalhes,
        )

        NotificacaoService.enviar_para_admins(
            db,
            "Pagamento realizado",
            f"{conta.descricao or 'Despesa'} — {_moeda(conta.valor)}",
        )

        if comprovante_base64:
            ContaPagarEventoService.registrar(
                db, conta.id, "COMPROVANTE_ANEXADO",
                usuario_id=usuario_id, dispositivo=dispositivo,
            )
            NotificacaoService.enviar_para_admins(
                db,
                "Comprovante enviado",
                f"{conta.descricao or 'Despesa'} — {_moeda(conta.valor)}",
                excluir_usuario_id=usuario_id,
            )

        return conta

    @staticmethod
    def trocar_comprovante(
        db: Session,
        conta_id: int,
        comprovante_base64: str,
        comprovante_nome: str | None = None,
        comprovante_tipo: str | None = None,
        usuario_id: int | None = None,
        dispositivo: str | None = None,
    ):
        conta = ContaPagarRepository.buscar_por_id(
            db,
            conta_id,
        )

        if not conta:
            raise Exception("Conta não encontrada.")

        if conta.status != StatusContaPagar.PAGO.value:
            raise Exception(
                "Só é possível trocar o comprovante de uma conta já paga."
            )

        conta.comprovante_pagamento = base64.b64decode(comprovante_base64)
        conta.comprovante_pagamento_nome = comprovante_nome
        conta.comprovante_pagamento_tipo = comprovante_tipo

        conta = ContaPagarRepository.atualizar(
            db,
            conta,
        )

        ContaPagarEventoService.registrar(
            db, conta.id, "COMPROVANTE_TROCADO",
            usuario_id=usuario_id, dispositivo=dispositivo,
        )

        NotificacaoService.enviar_para_admins(
            db,
            "Comprovante enviado",
            f"{conta.descricao or 'Despesa'} — {_moeda(conta.valor)}",
            excluir_usuario_id=usuario_id,
        )

        return conta

    @staticmethod
    def cancelar(
        db: Session,
        conta_id: int,
        usuario_id: int | None = None,
        dispositivo: str | None = None,
    ):
        """Cancela uma despesa (pendente ou ja paga) -- diferente de
        excluir(), o registro continua existindo com status CANCELADO,
        preservando o historico. Quem decide se isso pode rodar direto
        ou precisa de aprovacao e a camada de API (ver
        api/v1/contas_pagar.py e app/services/aprovacao_service.py)."""

        conta = ContaPagarRepository.buscar_por_id(
            db,
            conta_id,
        )

        if not conta:
            raise Exception("Conta não encontrada.")

        if conta.status == StatusContaPagar.CANCELADO.value:
            raise Exception("Conta já está cancelada.")

        conta.status = StatusContaPagar.CANCELADO.value

        conta = ContaPagarRepository.atualizar(
            db,
            conta,
        )

        ContaPagarEventoService.registrar(
            db, conta.id, "CANCELADA",
            usuario_id=usuario_id, dispositivo=dispositivo,
        )

        return conta

    @staticmethod
    def excluir(
        db: Session,
        conta_id: int,
    ):

        conta = ContaPagarRepository.buscar_por_id(
            db,
            conta_id,
        )

        if not conta:
            raise Exception("Conta não encontrada.")

        if conta.status == StatusContaPagar.PAGO.value:
            raise Exception(
                "Não é possível excluir uma despesa já paga. "
                "Use cancelar em vez de excluir."
            )

        ContaPagarRepository.excluir(db, conta)
