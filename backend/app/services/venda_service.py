import threading
import traceback
from datetime import datetime

from sqlalchemy.orm import Session

from app.enums.status_venda import StatusVenda
from app.models.venda import Venda
from app.models.item_venda import ItemVenda
from app.models.produto import Produto
from app.models.cliente import Cliente
from app.models.movimento_estoque import MovimentoEstoque
from app.models.movimento_caixa import MovimentoCaixa
from app.models.movimento_fiado import MovimentoFiado

from app.repositories.venda_repository import VendaRepository
from app.repositories.item_venda_repository import (
    ItemVendaRepository,
)
from app.repositories.caixa_repository import CaixaRepository
from app.repositories.estoque_loja_repository import EstoqueLojaRepository
from app.repositories.kit_item_repository import KitItemRepository
from app.repositories.movimento_fiado_repository import (
    MovimentoFiadoRepository,
)

from app.services.movimento_fiado_service import (
    MovimentoFiadoService,
    _verificar_limite_credito,
)
from app.services.notificacao_service import NotificacaoService, nome_do_usuario
from app.services.cliente_service import ClienteService
from app.services.configuracao_service import ConfiguracaoService
from app.services.whatsapp_service import WhatsappService


def _itens_para_baixa_estoque(db: Session, produto: Produto, quantidade: int):
    """Quem de fato tem estoque debitado/devolvido por essa venda --
    pra um produto normal e' ele mesmo; pra um kit/combo (Produto.eh_kit),
    sao os componentes (KitItem), cada um multiplicado pela quantidade
    configurada no kit. O kit em si nunca tem estoque proprio tocado."""

    if not produto.eh_kit:
        return [(produto, quantidade)]

    itens_kit = KitItemRepository.listar_por_kit(db, produto.id)

    return [
        (item.componente, item.quantidade * quantidade)
        for item in itens_kit
        if item.componente is not None
    ]


def _moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "_").replace(".", ",").replace(
        "_", "."
    )


def _enviar_comprovante_whatsapp(db: Session, venda: Venda) -> None:
    """Manda um resumo em texto da venda pro WhatsApp do cliente,
    assim que a venda e finalizada -- so quando a integracao e essa
    automacao especifica estao ligadas em Configuracoes, e o cliente
    tem telefone cadastrado. Nunca levanta excecao: uma falha aqui
    nao pode desfazer nem atrasar a venda, que ja foi commitada."""

    config = ConfiguracaoService.buscar(db)

    if not config.whatsapp_ativo or not config.whatsapp_comprovante_venda_ativo:
        return

    cliente = (
        db.query(Cliente)
        .filter(Cliente.id == venda.cliente_id)
        .first()
    )

    if not cliente or not cliente.telefone:
        return

    itens = (
        db.query(ItemVenda, Produto.nome)
        .join(Produto, Produto.id == ItemVenda.produto_id)
        .filter(ItemVenda.venda_id == venda.id)
        .all()
    )

    linhas_itens = "\n".join(
        f"• {item.quantidade}x {nome} — {_moeda(item.subtotal)}"
        for item, nome in itens
    )

    nome_loja = config.nome_loja or "Vertex ERP"

    texto = (
        f"*{nome_loja}* — comprovante da sua compra\n\n"
        f"{linhas_itens}\n\n"
        f"*Total: {_moeda(venda.valor_total)}*\n"
        f"Forma de pagamento: {venda.forma_pagamento}\n\n"
        f"Obrigado pela preferência! 🙂"
    )

    WhatsappService.enviar_mensagem(db, cliente.telefone, texto)


def _enviar_comprovante_whatsapp_em_segundo_plano(venda_id: int) -> None:
    """Roda _enviar_comprovante_whatsapp numa thread separada, fora do
    caminho critico da finalizacao da venda -- o Z-API pode demorar
    ate 10s pra responder (timeout de proposito, ver
    WhatsappService._TIMEOUT_SEGUNDOS), e isso nao pode virar 10s a
    mais de espera no PDV toda vez que uma venda com cliente+telefone
    fecha. Abre sua propria sessao de banco porque a sessao da
    requisicao original ja fecha (ver get_db) antes dessa thread
    rodar de verdade -- mesmo motivo do whatsapp_lembrete_service.py."""

    from app.database.session import SessionLocal

    db = SessionLocal()

    try:
        venda = VendaRepository.buscar_por_id(db, venda_id)

        if venda:
            _enviar_comprovante_whatsapp(db, venda)

    except Exception:
        pass

    finally:
        db.close()


def _parcelas_pagamento(venda_ou_dados, valor_total):
    """Monta a lista de (forma, valor) que compoem o pagamento da
    venda — 1 parcela na maioria dos casos, ou 2 quando a venda foi
    dividida (ex: parte dinheiro parte pix, ou entrada + resto fiado).
    Serve tanto pra criar quanto pra estornar, pra nao duplicar essa
    conta em dois lugares."""

    forma_2 = getattr(venda_ou_dados, "forma_pagamento_2", None)
    valor_2 = getattr(venda_ou_dados, "valor_forma_2", None)

    forma_1 = venda_ou_dados.forma_pagamento
    if hasattr(forma_1, "value"):
        forma_1 = forma_1.value

    if hasattr(forma_2, "value"):
        forma_2 = forma_2.value

    if not forma_2 or not valor_2:
        return [(forma_1, valor_total)]

    valor_1 = valor_total - valor_2

    parcelas = []

    if valor_1 > 0:
        parcelas.append((forma_1, valor_1))

    parcelas.append((forma_2, valor_2))

    return parcelas


class VendaService:

    @staticmethod
    def listar(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        loja_id: int | None = None,
        data_inicio=None,
        data_fim=None,
        usuario_id: int | None = None,
        cliente_id: int | None = None,
    ):
        return VendaRepository.listar(
            db, skip, limit, loja_id, data_inicio, data_fim, usuario_id, cliente_id
        )

    @staticmethod
    def resumo_vendedores(db: Session, data_inicio, data_fim, loja_id: int | None = None):
        """Quanto cada usuário vendeu no período (vendas finalizadas),
        menos o que foi devolvido dessas vendas. Cada vendedora entra
        com o próprio login, então o vendedor é o usuário da venda."""

        from datetime import timedelta

        from sqlalchemy import func

        from app.models.devolucao import Devolucao
        from app.models.user import User

        fim = data_fim + timedelta(days=1)

        filtros = [
            Venda.status == StatusVenda.FINALIZADA.value,
            Venda.data >= data_inicio,
            Venda.data < fim,
        ]
        if loja_id is not None:
            filtros.append(Venda.loja_id == loja_id)

        devolvido_por_venda = (
            db.query(
                Devolucao.venda_id.label("venda_id"),
                func.sum(Devolucao.valor_total).label("valor"),
            )
            .group_by(Devolucao.venda_id)
            .subquery()
        )

        linhas = (
            db.query(
                Venda.usuario_id,
                User.nome,
                func.count(Venda.id),
                func.coalesce(func.sum(Venda.valor_total), 0),
                func.coalesce(func.sum(devolvido_por_venda.c.valor), 0),
            )
            .outerjoin(User, User.id == Venda.usuario_id)
            .outerjoin(devolvido_por_venda, devolvido_por_venda.c.venda_id == Venda.id)
            .filter(*filtros)
            .group_by(Venda.usuario_id, User.nome)
            .all()
        )

        resultado = [
            {
                "usuario_id": usuario_id,
                "usuario_nome": nome,
                "quantidade_vendas": quantidade,
                "total_vendido": vendido,
                "total_devolvido": devolvido,
                "total_liquido": vendido - devolvido,
            }
            for usuario_id, nome, quantidade, vendido, devolvido in linhas
        ]

        return sorted(resultado, key=lambda r: r["total_liquido"], reverse=True)

    @staticmethod
    def buscar(
        db: Session,
        venda_id: int,
    ):
        return VendaRepository.buscar_por_id(
            db,
            venda_id,
        )

    @staticmethod
    def montar_comprovante(db: Session, venda_id: int):
        """Junta tudo que o comprovante de uma venda precisa (cliente,
        saldo devedor atualizado, nome dos produtos) numa unica
        estrutura -- evita o frontend ter que combinar varias
        chamadas so pra montar o PDF."""

        venda = VendaRepository.buscar_por_id(db, venda_id)

        if not venda:
            raise Exception("Venda não encontrada.")

        cliente = None
        saldo_devedor = None

        if venda.cliente_id:
            cliente = (
                db.query(Cliente)
                .filter(Cliente.id == venda.cliente_id)
                .first()
            )
            saldo_devedor = MovimentoFiadoRepository.saldo_por_cliente(
                db, venda.cliente_id
            )

        tem_fiado = "PRAZO" in (
            venda.forma_pagamento, venda.forma_pagamento_2
        )

        itens = [
            {
                "produto_id": item.produto_id,
                "nome": item.produto.nome if item.produto else "Produto removido",
                "quantidade": item.quantidade,
                "valor_unitario": item.valor_unitario,
                "subtotal": item.subtotal,
            }
            for item in venda.itens
        ]

        return {
            "venda_id": venda.id,
            "data": venda.data,
            "usuario_nome": venda.usuario_nome,
            "cliente_id": venda.cliente_id,
            "cliente_nome": cliente.nome if cliente else None,
            "cliente_cpf_cnpj": cliente.cpf_cnpj if cliente else None,
            "cliente_telefone": cliente.telefone if cliente else None,
            "cliente_email": cliente.email if cliente else None,
            "itens": itens,
            "desconto": venda.desconto,
            "valor_total": venda.valor_total,
            "forma_pagamento": venda.forma_pagamento,
            "forma_pagamento_2": venda.forma_pagamento_2,
            "valor_forma_2": venda.valor_forma_2,
            "observacao": venda.observacao,
            "situacao": "FIADO" if tem_fiado else "PAGO",
            "saldo_devedor_cliente": saldo_devedor,
        }

    @staticmethod
    def criar(
        db: Session,
        dados,
        usuario_id: int,
        loja_id: int | None = None,
        pode_alterar_preco: bool = False,
    ):

        # Toda venda (qualquer forma de pagamento) precisa de um caixa
        # aberto -- mesmo parcela que nao mexe fisicamente na gaveta
        # (pix/cartao/prazo) gera um MovimentoCaixa preso a esse caixa,
        # pra aparecer certinho no fechamento do turno (ver loop de
        # _parcelas_pagamento logo abaixo).
        caixa = CaixaRepository.buscar_aberto(
            db, usuario_id, loja_id, para_atualizar=True
        )

        # Reenvio da MESMA venda (resposta anterior se perdeu: timeout,
        # rede caiu) -- devolve a que ja foi gravada em vez de vender de
        # novo. Checado depois da trava do caixa: dois reenvios
        # simultaneos do mesmo operador ficam em fila e o segundo ja
        # enxerga a venda do primeiro.
        chave = getattr(dados, "chave_idempotencia", None)

        if chave:
            ja_gravada = (
                db.query(Venda)
                .filter(Venda.chave_idempotencia == chave)
                .first()
            )

            if ja_gravada:
                return ja_gravada

        if not caixa:
            raise Exception(
                "Não existe caixa aberto. Abra o caixa antes de "
                "registrar uma venda."
            )

        try:

            forma_pagamento = dados.forma_pagamento.value

            forma_pagamento_2 = (
                dados.forma_pagamento_2.value
                if dados.forma_pagamento_2
                else None
            )

            if forma_pagamento_2 == forma_pagamento:
                raise Exception(
                    "A segunda forma de pagamento precisa ser "
                    "diferente da primeira."
                )

            tem_prazo = (
                forma_pagamento == "PRAZO"
                or forma_pagamento_2 == "PRAZO"
            )

            if tem_prazo and dados.cliente_id is None:
                raise Exception(
                    "Venda a prazo exige selecionar um cliente."
                )

            ClienteService.recusar_se_negativado(db, dados.cliente_id)

            venda = Venda(
                cliente_id=dados.cliente_id,
                usuario_id=usuario_id,
                loja_id=loja_id,
                observacao=dados.observacao,
                desconto=dados.desconto,
                forma_pagamento=forma_pagamento,
                forma_pagamento_2=forma_pagamento_2,
                valor_forma_2=(
                    dados.valor_forma_2
                    if dados.valor_forma_2
                    else None
                ),
                data_vencimento=dados.data_vencimento,
                status="FINALIZADA",
                chave_idempotencia=chave,
            )

            VendaRepository.criar(
                db,
                venda,
            )

            valor_total = 0
            produtos_com_estoque_baixo = []

            for item in dados.itens:

                produto = (
                    db.query(Produto)
                    .filter(
                        Produto.id == item.produto_id
                    )
                    .first()
                )

                if produto is None:
                    raise Exception(
                        f"Produto {item.produto_id} não encontrado."
                    )

                # o preco vem do terminal -- sem essa checagem qualquer
                # operador (ou o app, com o token dele) vendia a qualquer
                # preco. preco_efetivo ja considera promocao vigente.
                if (
                    not pode_alterar_preco
                    and item.valor_unitario != produto.preco_efetivo
                ):
                    raise Exception(
                        f"O preço de {produto.nome} mudou para "
                        f"{_moeda(produto.preco_efetivo)}. Atualize o "
                        "item no carrinho e tente de novo."
                    )

                # checa/baixa o estoque da LOJA que esta vendendo, nao
                # o agregado entre lojas -- senao a Filial conseguiria
                # vender um produto que so tem estoque na Matriz (ou
                # vice-versa). Pra kit/combo, quem baixa e' os
                # componentes (ver _itens_para_baixa_estoque), nao o
                # kit em si.
                for produto_baixa, quantidade_baixa in _itens_para_baixa_estoque(
                    db, produto, item.quantidade
                ):

                    estoque_atual_loja = (
                        EstoqueLojaRepository.obter_ou_criar(
                            db, produto_baixa.id, loja_id
                        ).quantidade
                        if loja_id is not None else produto_baixa.estoque
                    )

                    if estoque_atual_loja < quantidade_baixa:
                        raise Exception(
                            f"Estoque insuficiente para {produto_baixa.nome}."
                        )

                subtotal = item.valor_unitario * item.quantidade

                item_venda = ItemVenda(
                    venda_id=venda.id,
                    produto_id=produto.id,
                    quantidade=item.quantidade,
                    valor_unitario=item.valor_unitario,
                    subtotal=subtotal,
                )

                ItemVendaRepository.criar(
                    db,
                    item_venda,
                )

                # Baixa do estoque (automatica, registrada no historico)
                for produto_baixa, quantidade_baixa in _itens_para_baixa_estoque(
                    db, produto, item.quantidade
                ):

                    estoque_atual_loja = (
                        EstoqueLojaRepository.obter_ou_criar(
                            db, produto_baixa.id, loja_id
                        ).quantidade
                        if loja_id is not None else produto_baixa.estoque
                    )

                    EstoqueLojaRepository.ajustar(
                        db, produto_baixa, loja_id, -quantidade_baixa
                    )

                    if (
                        estoque_atual_loja - quantidade_baixa
                        <= produto_baixa.estoque_minimo
                    ):
                        produtos_com_estoque_baixo.append(produto_baixa)

                    db.add(produto_baixa)

                    db.add(
                        MovimentoEstoque(
                            produto_id=produto_baixa.id,
                            usuario_id=usuario_id,
                            loja_id=loja_id,
                            tipo="SAIDA",
                            quantidade=quantidade_baixa,
                            motivo=f"Venda #{venda.id}",
                        )
                    )

                valor_total += subtotal

            venda.valor_total = (
                valor_total
                - dados.desconto
            )

            # desconto (positivo) maior que o subtotal deixaria a
            # venda com total negativo -- isso "vira" um estorno
            # disfarcado de venda normal (dreno o saldo_final do caixa
            # sem passar pelo fluxo de cancelamento/estorno de
            # verdade). Acrescimo (desconto negativo) nao tem esse
            # risco, so aumenta o total.
            if venda.valor_total < 0:
                raise Exception(
                    "O desconto não pode ser maior que o valor "
                    "total da venda."
                )

            if (
                venda.valor_forma_2 is not None
                and not (0 < venda.valor_forma_2 < venda.valor_total)
            ):
                raise Exception(
                    "O valor da segunda forma de pagamento precisa "
                    "ser maior que zero e menor que o total da venda."
                )

            db.add(venda)

            # so dinheiro fisico mexe no saldo do caixa; pix/cartao/
            # prazo nao entram na gaveta, mas o movimento fica
            # registrado pra aparecer no fechamento do caixa. Quando a
            # venda foi dividida em 2 formas, cada parcela gera seu
            # proprio movimento — cada uma com a forma e o valor que
            # de fato corresponde a ela.
            for forma_parcela, valor_parcela in _parcelas_pagamento(
                venda, venda.valor_total
            ):

                if forma_parcela == "DINHEIRO":
                    caixa.saldo_final += valor_parcela
                    db.add(caixa)

                db.add(
                    MovimentoCaixa(
                        caixa_id=caixa.id,
                        usuario_id=usuario_id,
                        tipo="VENDA",
                        valor=valor_parcela,
                        forma_pagamento=forma_parcela,
                        descricao=f"Venda #{venda.id}",
                    )
                )

                # a parcela a prazo vira lancamento de compra no
                # caderninho do cliente (mesma transacao, atomico
                # com o resto)
                if forma_parcela == "PRAZO":
                    MovimentoFiadoService.criar_compra_da_venda(
                        db,
                        venda,
                        usuario_id,
                        valor=valor_parcela,
                    )

            db.commit()

        except Exception as e:

            db.rollback()

            raise Exception(str(e))

        # Daqui pra baixo a venda JA esta gravada: nenhum erro de aviso
        # (notificacao, limite de credito, WhatsApp) pode virar HTTP 400
        # -- o caixa veria "erro", reenviaria e a venda sairia em dobro.
        try:
            VendaService._avisos_pos_venda(db, venda, produtos_com_estoque_baixo)
        except Exception:
            traceback.print_exc()
            db.rollback()

        db.refresh(venda)

        return venda

    @staticmethod
    def _avisos_pos_venda(db: Session, venda: Venda, produtos_com_estoque_baixo):

        db.refresh(venda)

        for produto in produtos_com_estoque_baixo:

            db.refresh(produto)

            NotificacaoService.enviar_para_admins(
                db,
                "Produto acabando",
                f"{produto.nome} está com estoque baixo "
                f"({produto.estoque} un.).",
            )

        if venda.cliente_id and "PRAZO" in (
            venda.forma_pagamento, venda.forma_pagamento_2
        ):
            _verificar_limite_credito(db, venda.cliente_id)

        if venda.cliente_id:
            threading.Thread(
                target=_enviar_comprovante_whatsapp_em_segundo_plano,
                args=(venda.id,),
                daemon=True,
            ).start()

        nome_cliente = None

        if venda.cliente_id:
            cliente_venda = (
                db.query(Cliente)
                .filter(Cliente.id == venda.cliente_id)
                .first()
            )
            nome_cliente = cliente_venda.nome if cliente_venda else None

        no_fiado = "PRAZO" in (
            venda.forma_pagamento, venda.forma_pagamento_2
        )

        NotificacaoService.enviar_para_admins(
            db,
            "Venda no fiado" if no_fiado else "Nova venda",
            f"Venda #{venda.id} — {_moeda(venda.valor_total)}"
            + (f" ({nome_cliente})" if nome_cliente else ""),
        )

    # ==================================================
    # VENDA SUSPENSA (carrinho salvo pra retomar depois -- status
    # ABERTA, nunca mexe em estoque/caixa/notificacao, so' vira
    # "de verdade" quando for retomada e finalizada via criar())
    # ==================================================

    @staticmethod
    def suspender(
        db: Session,
        dados,
        usuario_id: int,
        loja_id: int | None = None,
    ):
        ClienteService.recusar_se_negativado(db, dados.cliente_id)

        venda = Venda(
            cliente_id=dados.cliente_id,
            usuario_id=usuario_id,
            loja_id=loja_id,
            desconto=dados.desconto,
            status=StatusVenda.ABERTA.value,
        )

        VendaRepository.criar(db, venda)

        valor_total = 0

        for item in dados.itens:

            subtotal = item.valor_unitario * item.quantidade

            ItemVendaRepository.criar(
                db,
                ItemVenda(
                    venda_id=venda.id,
                    produto_id=item.produto_id,
                    quantidade=item.quantidade,
                    valor_unitario=item.valor_unitario,
                    subtotal=subtotal,
                ),
            )

            valor_total += subtotal

        venda.valor_total = valor_total - dados.desconto

        db.add(venda)
        db.commit()
        db.refresh(venda)

        # response_model da rota e' VendaSuspensaResponse, nao
        # VendaResponse: uma venda ABERTA nao tem forma_pagamento
        # de verdade ainda (esse campo nem e' setado aqui, fica no
        # default "AVISTA" da coluna, que nao e' um valor valido do
        # enum FormaPagamento usado por VendaResponse)
        return VendaService._serializar_suspensa(db, venda)

    @staticmethod
    def listar_suspensas(db: Session, loja_id: int | None = None):

        query = db.query(Venda).filter(
            Venda.status == StatusVenda.ABERTA.value
        )

        if loja_id is not None:
            query = query.filter(Venda.loja_id == loja_id)

        vendas = query.order_by(Venda.id.desc()).all()

        return [
            VendaService._serializar_suspensa(db, venda) for venda in vendas
        ]

    @staticmethod
    def _serializar_suspensa(db: Session, venda: Venda):

        itens = []

        for item in venda.itens:

            produto = (
                db.query(Produto)
                .filter(Produto.id == item.produto_id)
                .first()
            )

            itens.append({
                "produto_id": item.produto_id,
                "codigo": produto.codigo if produto else None,
                "nome": produto.nome if produto else "Produto removido",
                "quantidade": item.quantidade,
                "valor_unitario": item.valor_unitario,
                "estoque": produto.estoque if produto else None,
            })

        return {
            "id": venda.id,
            "cliente_id": venda.cliente_id,
            "cliente_nome": venda.cliente.nome if venda.cliente else None,
            "data": venda.data,
            "desconto": venda.desconto,
            "itens": itens,
        }

    @staticmethod
    def excluir_suspensa(db: Session, venda_id: int):

        venda = VendaRepository.buscar_por_id(db, venda_id)

        if venda is None:
            return False

        if venda.status != StatusVenda.ABERTA.value:
            raise Exception("Essa venda não está suspensa.")

        VendaRepository.excluir(db, venda)

        return True

    @staticmethod
    def excluir(
        db: Session,
        venda_id: int,
        usuario_id: int,
        motivo: str | None = None,
    ):

        # FOR UPDATE: dois cancelamentos simultaneos da mesma venda
        # (dois terminais, duplo clique) passavam os dois pela checagem
        # de status e estornavam estoque/caixa/fiado em dobro
        venda = (
            db.query(Venda)
            .filter(Venda.id == venda_id)
            .with_for_update()
            .first()
        )

        if venda is None:
            return False

        if venda.status == StatusVenda.CANCELADA.value:
            raise Exception("Essa venda já está cancelada.")

        # venda suspensa nunca baixou estoque nem entrou no caixa --
        # "cancelar" ela aqui devolveria estoque que nunca saiu
        if venda.status != StatusVenda.FINALIZADA.value:
            raise Exception(
                "Essa venda está suspensa, não finalizada. Exclua a "
                "venda suspensa em vez de cancelar."
            )

        # cancelar devolveria de novo o estoque/dinheiro dos itens que
        # ja voltaram numa devolucao parcial
        from app.models.devolucao import Devolucao

        if db.query(Devolucao.id).filter(Devolucao.venda_id == venda.id).first():
            raise Exception(
                "Essa venda já tem devolução registrada. Para desfazer o "
                "resto, faça uma devolução dos itens que faltam."
            )

        # Toda parcela (dinheiro ou nao) gera um MovimentoCaixa de
        # ESTORNO -- e MovimentoCaixa.caixa_id e obrigatorio -- entao
        # o cancelamento sempre precisa de um caixa aberto pra
        # registrar o estorno, mesmo quando a venda foi 100% pix/
        # cartao/prazo e nenhum dinheiro fisico esta envolvido.
        # venda lancada pela ficha do cliente (compra fiada a mao, ver
        # MovimentoFiadoService.criar): sem itens e sem movimento no
        # caixa -- cancelar so' desfaz o fiado, nao estorna caixa
        venda_manual = not venda.itens

        if not venda_manual and not CaixaRepository.buscar_aberto(
            db, usuario_id, venda.loja_id, para_atualizar=True
        ):
            raise Exception(
                "O caixa já está fechado. Abra um caixa antes de "
                "cancelar essa venda para que o estorno seja "
                "registrado corretamente."
            )

        # Devolve o estoque (automatico, registrado no historico)
        for item in venda.itens:

            produto = (
                db.query(Produto)
                .filter(
                    Produto.id == item.produto_id
                )
                .first()
            )

            if produto:

                for produto_devolve, quantidade_devolve in _itens_para_baixa_estoque(
                    db, produto, item.quantidade
                ):

                    EstoqueLojaRepository.ajustar(
                        db, produto_devolve, venda.loja_id, quantidade_devolve
                    )

                    db.add(produto_devolve)

                    db.add(
                        MovimentoEstoque(
                            produto_id=produto_devolve.id,
                            usuario_id=usuario_id,
                            loja_id=venda.loja_id,
                            tipo="ENTRADA",
                            quantidade=quantidade_devolve,
                            motivo=f"Estorno da venda #{venda_id}",
                        )
                    )

        # Estorna cada parcela do pagamento — normalmente so 1, mas
        # pode ser 2 quando a venda foi dividida entre duas formas
        for forma_parcela, valor_parcela in _parcelas_pagamento(
            venda, venda.valor_total
        ):

            # Toda parcela gera um MovimentoCaixa de ESTORNO -- o
            # check no topo do metodo ja garante que existe um caixa
            # aberto. So dinheiro fisico mexe no saldo da gaveta
            # (pix/cartao/prazo nunca afetaram saldo_final na criacao,
            # entao tambem nao devem afetar no estorno).
            caixa = (
                None if venda_manual else CaixaRepository.buscar_aberto(
                    db, usuario_id, venda.loja_id, para_atualizar=True
                )
            )

            if caixa:

                if forma_parcela == "DINHEIRO":
                    caixa.saldo_final -= valor_parcela
                    db.add(caixa)

                db.add(
                    MovimentoCaixa(
                        caixa_id=caixa.id,
                        usuario_id=usuario_id,
                        tipo="ESTORNO",
                        valor=-valor_parcela,
                        forma_pagamento=forma_parcela,
                        descricao=f"Estorno da venda #{venda_id}",
                    )
                )

            # Zera a divida do caderninho referente a essa parcela, se
            # ela tiver sido a prazo. Se o cliente ja tiver pago parte
            # do saldo (de forma geral, nao especifica dessa venda —
            # o caderninho e um saldo unico corrido), o estorno nao
            # pode "devolver" mais do que ele ainda deve, senao o
            # saldo fica negativo indevidamente.
            if forma_parcela == "PRAZO" and venda.cliente_id:

                saldo_atual = (
                    MovimentoFiadoRepository.saldo_por_cliente(
                        db,
                        venda.cliente_id,
                    )
                )

                valor_estorno = min(valor_parcela, saldo_atual)

                if valor_estorno > 0:

                    db.add(
                        MovimentoFiado(
                            cliente_id=venda.cliente_id,
                            venda_id=None,
                            usuario_id=usuario_id,
                            tipo="PAGAMENTO",
                            valor=valor_estorno,
                            descricao=(
                                f"Estorno da venda #{venda_id}"
                            ),
                        )
                    )

        # A venda NUNCA e apagada -- so muda de status. Fica no banco
        # pra sempre com a trilha de quem cancelou, quando e por que,
        # preservando historico do cliente e rastreabilidade dos
        # lancamentos de fiado/caixa que ja referenciam essa venda.
        venda.status = StatusVenda.CANCELADA.value
        venda.cancelado_em = datetime.now()
        venda.cancelado_por_id = usuario_id
        venda.motivo_cancelamento = motivo

        db.add(venda)

        db.commit()

        NotificacaoService.enviar_para_admins(
            db,
            "Venda cancelada",
            f"Venda #{venda.id} — {_moeda(venda.valor_total)}, cancelada por "
            f"{nome_do_usuario(db, usuario_id)}"
            + (f": {motivo}" if motivo else "."),
        )

        return True