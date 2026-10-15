from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.caixa import Caixa
from app.models.cliente import Cliente
from app.models.movimento_fiado import MovimentoFiado
from app.models.movimento_caixa import MovimentoCaixa
from app.models.venda import Venda
from app.repositories.cliente_repository import ClienteRepository
from app.repositories.caixa_repository import CaixaRepository
from app.repositories.movimento_fiado_repository import (
    MovimentoFiadoRepository,
)
from app.schemas.movimento_fiado import (
    MovimentoFiadoCreate,
    MovimentoFiadoUpdate,
)
from app.services.notificacao_service import NotificacaoService, moeda


def _ajustar_caixa_por_correcao(
    db: Session,
    usuario_id: int,
    cliente_nome: str,
    diferenca: Decimal,
    forma_pagamento: str,
    motivo: str,
    caixa_id_original: int | None = None,
) -> bool:
    """Reflete a correcao/exclusao de um PAGAMENTO de fiado no caixa --
    mesmo 'tipo' (RECEBIMENTO_FIADO) do lancamento original, so que com
    o valor da diferenca (negativo reduz, positivo aumenta), pra toda
    soma existente (CaixaService.resumo) continuar batendo sozinha,
    sem precisar conhecer um tipo novo 'estorno'.

    Vai no caixa onde o recebimento entrou se ele ainda estiver aberto
    (o dinheiro esta naquela gaveta, mesmo que quem corrige seja outro
    usuario); ja fechado ou recebimento antigo sem caixa_id, vai no
    caixa aberto de quem esta corrigindo.

    Devolve False (e nao mexe em nada) se nao houver caixa aberto pro
    usuario que esta corrigindo -- a correcao do fiado em si acontece
    de qualquer forma, so o ajuste automatico do caixa fica pendente
    (o chamador avisa o usuario disso)."""

    if diferenca == 0:
        return True

    caixa = None

    if caixa_id_original is not None:
        caixa = (
            db.query(Caixa)
            .filter(Caixa.id == caixa_id_original, Caixa.status == "ABERTO")
            .with_for_update()
            .first()
        )

    if not caixa:
        caixa = CaixaRepository.buscar_aberto(
            db, usuario_id, para_atualizar=True
        )

    if not caixa:
        return False

    if forma_pagamento == "DINHEIRO":
        caixa.saldo_final += diferenca
        db.add(caixa)

    db.add(
        MovimentoCaixa(
            caixa_id=caixa.id,
            usuario_id=usuario_id,
            tipo="RECEBIMENTO_FIADO",
            valor=diferenca,
            forma_pagamento=forma_pagamento,
            descricao=f"{motivo} - {cliente_nome}",
        )
    )

    return True


def _recusar_se_veio_de_venda(movimento: MovimentoFiado) -> None:
    """A compra no fiado gerada por uma venda so' pode sumir/mudar
    cancelando a venda (que tambem devolve estoque e estorna o caixa)
    -- editar/apagar direto aqui deixaria venda e caderninho
    discordando pra sempre."""

    if movimento.venda_id is not None:
        raise Exception(
            f"Este lançamento veio da venda #{movimento.venda_id}. "
            "Para corrigir, cancele a venda."
        )


def _verificar_limite_credito(db: Session, cliente_id: int):
    """Depois de uma compra a prazo, confere se o cliente passou do
    limite de credito cadastrado — se sim, avisa os administradores.
    Cliente sem limite definido (None) nunca dispara isso."""

    cliente = ClienteRepository.buscar_por_id(db, cliente_id)

    if not cliente or cliente.limite_credito is None:
        return

    saldo = MovimentoFiadoRepository.saldo_por_cliente(db, cliente_id)

    if saldo > cliente.limite_credito:
        NotificacaoService.enviar_para_admins(
            db,
            "Cliente inadimplente",
            f"{cliente.nome} passou do limite de crédito "
            f"(R$ {saldo:.2f} de R$ {cliente.limite_credito:.2f}).",
        )


class MovimentoFiadoService:

    @staticmethod
    def criar(
        db: Session,
        dados: MovimentoFiadoCreate,
        usuario_id: int,
        loja_id: int | None = None,
    ):

        # FOR UPDATE no cliente: serializa lancamentos do mesmo cliente
        # -- dois recebimentos simultaneos (dois terminais) passavam os
        # dois pela checagem de saldo e deixavam a divida negativa
        cliente = (
            db.query(Cliente)
            .filter(Cliente.id == dados.cliente_id)
            .with_for_update()
            .first()
        )

        if not cliente:
            raise Exception("Cliente não encontrado.")

        tipo = dados.tipo.upper()

        # HAVER: credito manual em favor do cliente (desconto, devolucao
        # etc.) -- reduz o saldo devedor igual um pagamento, mas nunca
        # mexe no caixa (nao e dinheiro recebido de verdade, ver abaixo).
        if tipo not in ("COMPRA", "PAGAMENTO", "HAVER"):
            raise Exception("Tipo de movimento inválido.")

        if tipo == "COMPRA" and cliente.negativado:
            raise Exception(
                f"{cliente.nome} está NEGATIVADO: não é possível lançar compra "
                "no fiado. Só um administrador pode desbloquear."
            )

        if dados.valor <= 0:
            _rotulo = {
                "COMPRA": "compra",
                "PAGAMENTO": "pagamento",
                "HAVER": "lançamento",
            }[tipo]
            raise Exception(
                f"Informe um valor de {_rotulo} maior que zero."
            )

        if tipo in ("PAGAMENTO", "HAVER"):

            saldo_atual = MovimentoFiadoRepository.saldo_por_cliente(
                db,
                dados.cliente_id,
            )

            if dados.valor > saldo_atual:
                raise Exception(
                    f"O valor (R$ {dados.valor:.2f}) é maior que o "
                    f"saldo devedor do cliente (R$ {saldo_atual:.2f})."
                )

        forma_pagamento = (
            dados.forma_pagamento.upper()
            if dados.forma_pagamento
            else None
        )

        # so registra no caixa quando for um pagamento de verdade
        # (recebido no balcao); ajustes internos do sistema (ex.:
        # estorno de venda fiado) nao informam forma_pagamento
        if tipo == "PAGAMENTO" and forma_pagamento:

            caixa = CaixaRepository.buscar_aberto(db, usuario_id, para_atualizar=True)

            if not caixa:
                raise Exception(
                    "Não existe caixa aberto. Abra o caixa antes de "
                    "registrar o recebimento."
                )

            if forma_pagamento == "DINHEIRO":
                caixa.saldo_final += dados.valor
                db.add(caixa)

            db.add(
                MovimentoCaixa(
                    caixa_id=caixa.id,
                    usuario_id=usuario_id,
                    tipo="RECEBIMENTO_FIADO",
                    valor=dados.valor,
                    forma_pagamento=forma_pagamento,
                    descricao=f"Pagamento fiado - {cliente.nome}",
                )
            )

        caixa_id = caixa.id if tipo == "PAGAMENTO" and forma_pagamento else None
        data = dados.data or datetime.now()
        venda_id = dados.venda_id

        # compra fiada lancada a mao (ver MovimentoFiadoCreate) vira
        # venda a prazo sem itens, na mesma transacao do fiado. Nao mexe
        # no caixa nem exige caixa aberto (a prazo nunca entra na gaveta,
        # e a data pode ser de outro dia) -- ver VendaService.excluir,
        # que sabe cancelar esse tipo de venda.
        if (
            tipo == "COMPRA"
            and getattr(dados, "registrar_venda", False)
            and venda_id is None
        ):
            venda = Venda(
                cliente_id=dados.cliente_id,
                usuario_id=usuario_id,
                loja_id=loja_id,
                data=data,
                valor_total=dados.valor,
                desconto=0,
                observacao=(dados.descricao or "Compra no fiado")[:255],
                forma_pagamento="PRAZO",
                status="FINALIZADA",
            )
            db.add(venda)
            db.flush()
            venda_id = venda.id

        movimento = MovimentoFiado(
            cliente_id=dados.cliente_id,
            venda_id=venda_id,
            usuario_id=usuario_id,
            caixa_id=caixa_id,
            tipo=tipo,
            valor=dados.valor,
            descricao=dados.descricao,
            forma_pagamento=forma_pagamento,
            data=data,
        )

        movimento = MovimentoFiadoRepository.criar(db, movimento)

        if tipo == "COMPRA":
            _verificar_limite_credito(db, dados.cliente_id)

        titulo, verbo = {
            "COMPRA": ("Compra no fiado", "comprou"),
            "PAGAMENTO": ("Recebimento de fiado", "pagou"),
            "HAVER": ("Haver lançado", "recebeu um haver de"),
        }[tipo]
        saldo = MovimentoFiadoRepository.saldo_por_cliente(
            db, dados.cliente_id
        )
        NotificacaoService.enviar_para_admins(
            db,
            titulo,
            f"{cliente.nome} {verbo} {moeda(dados.valor)}. "
            f"Saldo devedor: {moeda(saldo)}.",
        )

        return movimento

    @staticmethod
    def criar_compra_da_venda(
        db: Session, venda, usuario_id: int, valor: Decimal | None = None
    ):
        # 'valor' existe pra venda dividida em 2 formas de pagamento —
        # nesse caso so a parcela que foi de fato pro fiado deve virar
        # divida no caderninho, nao o total da venda inteira.

        movimento = MovimentoFiado(
            cliente_id=venda.cliente_id,
            venda_id=venda.id,
            usuario_id=usuario_id,
            tipo="COMPRA",
            valor=valor if valor is not None else venda.valor_total,
            descricao=f"Venda #{venda.id}",
        )

        db.add(movimento)

        return movimento

    @staticmethod
    def atualizar(
        db: Session,
        movimento_id: int,
        dados: MovimentoFiadoUpdate,
        usuario_id: int,
    ) -> tuple:
        """Corrige um lancamento errado (valor e/ou descricao). Se for
        um PAGAMENTO que tinha impactado o caixa, a diferenca de valor
        e refletida no caixa onde ele entrou (ou, ja fechado, no de quem
        esta corrigindo) -- devolve
        (movimento, caixa_ajustado) pra API poder avisar quando nao
        havia caixa aberto pra ajustar automaticamente."""

        movimento = MovimentoFiadoRepository.buscar_por_id(db, movimento_id)

        if not movimento:
            raise Exception("Lançamento não encontrado.")

        _recusar_se_veio_de_venda(movimento)

        if dados.valor is not None and dados.valor <= 0:
            raise Exception("Informe um valor maior que zero.")

        valor_antigo = movimento.valor
        caixa_ajustado = True

        if dados.valor is not None:
            movimento.valor = dados.valor

        if dados.descricao is not None:
            movimento.descricao = dados.descricao

        if (
            movimento.tipo == "PAGAMENTO"
            and movimento.forma_pagamento
            and dados.valor is not None
            and dados.valor != valor_antigo
        ):
            cliente = ClienteRepository.buscar_por_id(
                db, movimento.cliente_id
            )
            caixa_ajustado = _ajustar_caixa_por_correcao(
                db,
                usuario_id,
                cliente.nome if cliente else "cliente",
                dados.valor - valor_antigo,
                movimento.forma_pagamento,
                "Ajuste de fiado",
                movimento.caixa_id,
            )

        movimento = MovimentoFiadoRepository.atualizar(db, movimento)

        return movimento, caixa_ajustado

    @staticmethod
    def excluir(db: Session, movimento_id: int, usuario_id: int) -> bool:
        """Exclui um lancamento errado. Se era um PAGAMENTO que tinha
        impactado o caixa, estorna no caixa onde ele entrou (ou,
        ja fechado, no de quem esta excluindo) -- devolve False se nao havia caixa aberto (o
        lancamento e excluido de qualquer forma, so o estorno
        automatico do caixa fica pendente)."""

        movimento = MovimentoFiadoRepository.buscar_por_id(db, movimento_id)

        if not movimento:
            raise Exception("Lançamento não encontrado.")

        _recusar_se_veio_de_venda(movimento)

        caixa_ajustado = True

        if movimento.tipo == "PAGAMENTO" and movimento.forma_pagamento:
            cliente = ClienteRepository.buscar_por_id(
                db, movimento.cliente_id
            )
            caixa_ajustado = _ajustar_caixa_por_correcao(
                db,
                usuario_id,
                cliente.nome if cliente else "cliente",
                -movimento.valor,
                movimento.forma_pagamento,
                "Exclusão de fiado",
                movimento.caixa_id,
            )

        MovimentoFiadoRepository.excluir(db, movimento)

        return caixa_ajustado

    @staticmethod
    def listar(db: Session):
        return MovimentoFiadoRepository.listar(db)

    @staticmethod
    def listar_por_cliente(db: Session, cliente_id: int):
        return MovimentoFiadoRepository.listar_por_cliente(
            db,
            cliente_id,
        )

    @staticmethod
    def saldo_por_cliente(db: Session, cliente_id: int):
        return MovimentoFiadoRepository.saldo_por_cliente(
            db,
            cliente_id,
        )

    @staticmethod
    def saldo_total(db: Session):
        return MovimentoFiadoRepository.saldo_total(db)

    @staticmethod
    def ficha_cliente(db: Session, cliente_id: int):
        """Saldo + histórico completo de um cliente numa chamada só --
        usado pela tela de ficha do cliente."""

        cliente = ClienteRepository.buscar_por_id(db, cliente_id)

        if not cliente:
            raise Exception("Cliente não encontrado.")

        return {
            "cliente_id": cliente.id,
            "nome": cliente.nome,
            "saldo_devedor": MovimentoFiadoRepository.saldo_por_cliente(
                db, cliente_id,
            ),
            "movimentos": MovimentoFiadoRepository.listar_por_cliente(
                db, cliente_id,
            ),
        }

    @staticmethod
    def saldos_por_cliente(db: Session):
        return MovimentoFiadoRepository.saldos_por_cliente(db)
