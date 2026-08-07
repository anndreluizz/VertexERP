import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlalchemy.orm import Session

from app.services.configuracao_service import ConfiguracaoService

# generoso de proposito, mesma logica do timeout do WhatsappService --
# um servidor SMTP lento nao pode fazer o envio "falhar" por
# impaciencia.
_TIMEOUT_SEGUNDOS = 15


class EmailService:

    @staticmethod
    def enviar_email(
        db: Session,
        destinatario: str | None,
        assunto: str,
        corpo: str,
        anexo_bytes: bytes | None = None,
        anexo_nome: str = "comprovante.pdf",
    ) -> tuple[bool, str | None]:
        """Manda um e-mail via SMTP configurado em Configurações
        (credencial da própria loja -- Gmail, etc.), com anexo
        opcional. Nunca levanta exceção pra fora: devolve
        (sucesso, motivo_erro) pra quem chamou poder registrar no
        histórico de envio."""

        try:

            config = ConfiguracaoService.buscar(db)

            if not config.smtp_ativo:
                return False, "Integração de e-mail (SMTP) está desligada."

            if not config.smtp_host or not config.smtp_usuario or not config.smtp_senha:
                return False, "SMTP não configurado (host/usuário/senha)."

            if not destinatario:
                return False, "Cliente sem e-mail cadastrado."

            remetente = config.smtp_remetente or config.smtp_usuario

            mensagem = MIMEMultipart()
            mensagem["From"] = remetente
            mensagem["To"] = destinatario
            mensagem["Subject"] = assunto
            mensagem.attach(MIMEText(corpo, "plain", "utf-8"))

            if anexo_bytes:
                anexo = MIMEApplication(anexo_bytes, _subtype="pdf")
                anexo.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=anexo_nome,
                )
                mensagem.attach(anexo)

            with smtplib.SMTP(
                config.smtp_host, config.smtp_porta, timeout=_TIMEOUT_SEGUNDOS
            ) as servidor:
                servidor.starttls()
                servidor.login(config.smtp_usuario, config.smtp_senha)
                servidor.sendmail(
                    remetente, destinatario, mensagem.as_string()
                )

            return True, None

        except Exception as e:
            return False, str(e)
