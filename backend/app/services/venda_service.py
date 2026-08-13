from sqlalchemy.orm import Session

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
from app.repositories.movimento_fiado_repository import (
    MovimentoFiadoRepository,
)

from app.services.movimento_fiado_service import (
    MovimentoFiadoService,
    _verificar_limite_credito,
)
from app.services.notificacao_service import NotificacaoService
from app.services.configuracao_service import ConfiguracaoService
from app.services.whatsapp_service import WhatsappService


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
    def listar(db: Session):
        return VendaRepository.listar(db)

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
    ):

        caixa = CaixaRepository.buscar_aberto(db, usuario_id)

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

            venda = Venda(
                cliente_id=dados.cliente_id,
                usuario_id=usuario_id,
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

                if produto.estoque < item.quantidade:
                    raise Exception(
                        f"Estoque insuficiente para {produto.nome}."
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
                produto.estoque -= item.quantidade

                if produto.estoque <= produto.estoque_minimo:
                    produtos_com_estoque_baixo.append(produto)

                db.add(produto)

                db.add(
                    MovimentoEstoque(
                        produto_id=produto.id,
                        usuario_id=usuario_id,
                        tipo="SAIDA",
                        quantidade=item.quantidade,
                        motivo=f"Venda #{venda.id}",
                    )
                )

                valor_total += subtotal

            venda.valor_total = (
                valor_total
                - dados.desconto
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
                try:
                    _enviar_comprovante_whatsapp(db, venda)
                except Exception:
                    pass

            nome_cliente = None

            if venda.cliente_id:
                cliente_venda = (
                    db.query(Cliente)
                    .filter(Cliente.id == venda.cliente_id)
                    .first()
                )
                nome_cliente = cliente_venda.nome if cliente_venda else None

            NotificacaoService.enviar_para_admins(
                db,
                "Nova venda",
                f"Venda #{venda.id} — {_moeda(venda.valor_total)}"
                + (f" ({nome_cliente})" if nome_cliente else ""),
                excluir_usuario_id=usuario_id,
            )

            return venda

        except Exception as e:

            db.rollback()

            raise Exception(str(e))

    @staticmethod
    def excluir(
        db: Session,
        venda_id: int,
        usuario_id: int,
    ):

        venda = VendaRepository.buscar_por_id(
            db,
            venda_id,
        )

        if venda is None:
            return False

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

                produto.estoque += item.quantidade

                db.add(produto)

                db.add(
                    MovimentoEstoque(
                        produto_id=produto.id,
                        usuario_id=usuario_id,
                        tipo="ENTRADA",
                        quantidade=item.quantidade,
                        motivo=f"Estorno da venda #{venda_id}",
                    )
                )

        # Estorna cada parcela do pagamento — normalmente so 1, mas
        # pode ser 2 quando a venda foi dividida entre duas formas
        for forma_parcela, valor_parcela in _parcelas_pagamento(
            venda, venda.valor_total
        ):

            # Estorna o valor no caixa aberto, se a parcela tiver sido
            # em dinheiro (pix/cartao/prazo nao afetam a gaveta fisica)
            if forma_parcela == "DINHEIRO":

                caixa = CaixaRepository.buscar_aberto(db, usuario_id)

                if caixa:

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

        # Garante que nenhum lancamento antigo do fiado fique
        # apontando pra essa venda antes de apaga-la
        db.query(MovimentoFiado).filter(
            MovimentoFiado.venda_id == venda_id
        ).update({"venda_id": None})

        VendaRepository.excluir(
            db,
            venda,
        )

        db.commit()

        return True