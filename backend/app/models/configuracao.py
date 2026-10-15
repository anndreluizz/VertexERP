from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, LargeBinary, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Configuracao(Base):
    __tablename__ = "configuracoes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    nome_loja: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    cnpj_cpf: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    endereco: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    telefone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    pix_chave: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    pix_nome: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    pix_cidade: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    logo_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    # logo de verdade (bytes), pro cabecalho do comprovante --
    # logo_filename acima nunca foi ligado a upload nenhum, entao nao
    # tinha imagem de verdade pra usar; segue o mesmo padrao de
    # Cliente.foto (bytes direto no banco).
    logo: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True
    )

    @property
    def tem_logo(self) -> bool:
        return self.logo is not None

    # SMTP pra "Enviar por E-mail" do comprovante -- credencial de
    # terceiro (Gmail, etc.), sempre configurada pela loja, nunca
    # hardcoded.
    smtp_host: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    smtp_porta: Mapped[int] = mapped_column(
        Integer,
        default=587
    )

    smtp_usuario: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    smtp_senha: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    smtp_remetente: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    smtp_ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    # Integracao com WhatsApp (via Z-API) -- instance_id/token sao a
    # credencial da instancia conectada (QR code escaneado la no
    # Z-API), nunca ficam hardcoded nem expostos pro frontend fora
    # dessa tela de configuracao.
    whatsapp_instance_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    whatsapp_token: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    whatsapp_ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    whatsapp_lembrete_fiado_ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    whatsapp_lembrete_fiado_dias: Mapped[int] = mapped_column(
        Integer,
        default=30
    )

    whatsapp_comprovante_venda_ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    # dinheiro guardado fora dos caixas (cofre + banco), informado pelo
    # dono na Inteligencia de Negocios -- fora do ConfiguracaoResponse de
    # proposito (GET /configuracoes e' aberto a qualquer usuario)
    dinheiro_guardado: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True
    )

    dinheiro_guardado_em: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
