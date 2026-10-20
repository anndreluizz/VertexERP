from datetime import datetime

from sqlalchemy.orm import Session

from app.schemas.cliente import ClienteUpdate
from app.models.cliente import Cliente
from app.models.movimento_fiado import MovimentoFiado
from app.schemas.cliente import ClienteCreate
from app.repositories.cliente_repository import ClienteRepository
from app.repositories.movimento_fiado_repository import MovimentoFiadoRepository
from app.services.notificacao_service import NotificacaoService
from app.utils.imagem import decodificar_foto


class ClienteService:

    @staticmethod
    def criar(db: Session, dados: ClienteCreate, loja_id: int | None = None):

        if dados.cpf_cnpj:

            cliente = ClienteRepository.buscar_por_documento(
                db,
                dados.cpf_cnpj
            )

            if cliente:
                raise Exception("CPF/CNPJ já cadastrado.")

        novo_cliente = Cliente(
            nome=dados.nome,
            cpf_cnpj=dados.cpf_cnpj,
            telefone=dados.telefone,
            email=dados.email,
            endereco=dados.endereco,
            cidade=dados.cidade,
            estado=dados.estado,
            data_nascimento=dados.data_nascimento,
            limite_credito=dados.limite_credito,
            loja_id=loja_id,
            ativo=True

        )

        if dados.foto_base64:
            novo_cliente.foto = decodificar_foto(dados.foto_base64)

        cliente = ClienteRepository.criar(db, novo_cliente)

        NotificacaoService.enviar_para_admins(
            db, "Novo cliente", f"{cliente.nome} foi cadastrado."
        )

        return cliente

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100, loja_id: int | None = None):
        return ClienteRepository.listar(db, skip, limit, loja_id)

    @staticmethod
    def buscar_por_id(db: Session, cliente_id: int):
        return ClienteRepository.buscar_por_id(db, cliente_id)

    @staticmethod
    def atualizar(
            db: Session,
            cliente_id: int,
            dados: ClienteUpdate
    ):

        cliente = ClienteRepository.buscar_por_id(
            db,
            cliente_id
        )

        if not cliente:
            raise Exception("Cliente não encontrado.")

        campos = dados.model_dump(exclude_unset=True, exclude={"foto_base64"})

        for campo, valor in campos.items():
            setattr(cliente, campo, valor)

        if dados.foto_base64:
            cliente.foto = decodificar_foto(dados.foto_base64)

        return ClienteRepository.atualizar(db, cliente)

    @staticmethod
    def excluir(
            db: Session,
            cliente_id: int
    ):

        cliente = ClienteRepository.buscar_por_id(
            db,
            cliente_id
        )

        if not cliente:
            raise Exception("Cliente não encontrado.")

        cliente.ativo = False

        ClienteRepository.atualizar(db, cliente)

        return {
            "mensagem": "Cliente desativado com sucesso."
        }

    @staticmethod
    def reativar(
            db: Session,
            cliente_id: int
    ):

        cliente = ClienteRepository.buscar_por_id(
            db,
            cliente_id
        )

        if not cliente:
            raise Exception("Cliente não encontrado.")

        cliente.ativo = True

        ClienteRepository.atualizar(db, cliente)

        return {
            "mensagem": "Cliente reativado com sucesso."
        }

    @staticmethod
    def recusar_se_negativado(db: Session, cliente_id: int | None):
        """Negativado nao compra nada, nem a vista (decisao do dono) --
        chamado na venda, na venda suspensa e na compra manual no fiado.
        Receber pagamento dele continua liberado."""
        if cliente_id is None:
            return
        cliente = db.get(Cliente, cliente_id)
        if cliente is not None and cliente.negativado:
            raise Exception(
                f"{cliente.nome} está NEGATIVADO: não é possível vender para "
                "este cliente. Só um administrador pode desbloquear."
            )

    @staticmethod
    def negativar(db: Session, cliente_id: int, motivo: str, usuario_id: int):
        """Bloqueia o cliente e baixa o saldo devedor como PERDA: sai do
        fiado em aberto, mas fica no historico. Pra receber depois, exclui
        o lancamento de PERDA na ficha e registra o pagamento."""
        cliente = (
            db.query(Cliente).filter(Cliente.id == cliente_id)
            .with_for_update().first()
        )
        if not cliente:
            raise Exception("Cliente não encontrado.")
        if cliente.negativado:
            raise Exception(f"{cliente.nome} já está negativado.")

        saldo = MovimentoFiadoRepository.saldo_por_cliente(db, cliente_id)
        if saldo > 0:
            db.add(MovimentoFiado(
                cliente_id=cliente_id,
                usuario_id=usuario_id,
                tipo="PERDA",
                valor=saldo,
                descricao=f"Dívida baixada como perda: {motivo}"[:255],
                data=datetime.now(),
            ))

        cliente.negativado = True
        cliente.negativado_em = datetime.now()
        cliente.negativado_motivo = motivo
        db.commit()
        db.refresh(cliente)
        return cliente

    @staticmethod
    def desbloquear(db: Session, cliente_id: int):
        """Tira o bloqueio. A divida baixada continua como perda: pra
        cobrar de novo, exclui o lancamento de PERDA na ficha."""
        cliente = ClienteRepository.buscar_por_id(db, cliente_id)
        if not cliente:
            raise Exception("Cliente não encontrado.")
        cliente.negativado = False
        cliente.negativado_em = None
        cliente.negativado_motivo = None
        db.commit()
        db.refresh(cliente)
        return cliente

    # ==================================================
    # LGPD -- direito de acesso (exportar) e ao esquecimento (anonimizar)
    # ==================================================

    @staticmethod
    def exportar_dados_lgpd(db: Session, cliente_id: int):
        """Todos os dados pessoais guardados sobre um cliente, numa
        chamada só -- atende o direito de acesso/portabilidade da
        LGPD (Lei 13.709/2018, art. 18, II)."""

        cliente = ClienteRepository.buscar_por_id(db, cliente_id)

        if not cliente:
            raise Exception("Cliente não encontrado.")

        return {
            "cliente_id": cliente.id,
            "nome": cliente.nome,
            "cpf_cnpj": cliente.cpf_cnpj,
            "telefone": cliente.telefone,
            "email": cliente.email,
            "endereco": cliente.endereco,
            "cidade": cliente.cidade,
            "estado": cliente.estado,
            "data_nascimento": cliente.data_nascimento,
            "limite_credito": cliente.limite_credito,
            "tem_foto": cliente.tem_foto,
            "cadastrado_em": cliente.criado_em,
            "saldo_devedor_fiado": MovimentoFiadoRepository.saldo_por_cliente(
                db, cliente_id
            ),
            "movimentos_fiado": MovimentoFiadoRepository.listar_por_cliente(
                db, cliente_id
            ),
            "vendas": cliente.vendas,
            "observacoes": cliente.observacoes,
        }

    @staticmethod
    def anonimizar_dados_lgpd(db: Session, cliente_id: int):
        """Direito ao esquecimento (LGPD, art. 18, VI) -- apaga os
        dados PESSOAIS do cliente (nome, CPF/CNPJ, telefone, e-mail,
        endereço, data de nascimento, foto) e as observações
        escritas sobre ele, mas mantém o registro (id) e o histórico
        de vendas/movimentos de fiado intactos -- a loja tem uma
        razão legítima pra manter esses registros contábeis (LGPD
        art. 16, I: cumprimento de obrigação legal/regulatória). Sem
        os dados pessoais, esse histórico já deixa de identificar a
        pessoa por conta própria.

        Recusa enquanto houver saldo devedor em aberto: a loja ainda
        precisa saber quem deve, pra poder cobrar -- é a mesma lógica
        de exceção (art. 16, I/II) aplicada a uma dívida em aberto."""

        cliente = ClienteRepository.buscar_por_id(db, cliente_id)

        if not cliente:
            raise Exception("Cliente não encontrado.")

        saldo = MovimentoFiadoRepository.saldo_por_cliente(db, cliente_id)

        if saldo and saldo > 0:
            raise Exception(
                "Não é possível remover os dados: o cliente tem um "
                f"saldo devedor de R$ {saldo:.2f} em aberto. Quite o "
                "saldo (ou registre a perda) antes de remover os "
                "dados pessoais."
            )

        cliente.nome = "Cliente removido (LGPD)"
        cliente.cpf_cnpj = None
        cliente.telefone = None
        cliente.email = None
        cliente.endereco = None
        cliente.cidade = None
        cliente.estado = None
        cliente.data_nascimento = None
        cliente.limite_credito = None
        cliente.foto = None
        cliente.ativo = False

        for observacao in list(cliente.observacoes):
            db.delete(observacao)

        ClienteRepository.atualizar(db, cliente)

        return {
            "cliente_id": cliente.id,
            "mensagem": "Dados pessoais removidos com sucesso.",
        }
