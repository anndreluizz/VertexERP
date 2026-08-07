import requests
from sqlalchemy.orm import Session

from app.services.configuracao_service import ConfiguracaoService

# generoso de proposito -- Z-API as vezes demora um pouco mais que o
# normal, e um timeout curto demais faria a venda/checagem diaria
# "falhar" o envio por impaciencia, nao por erro de verdade.
_TIMEOUT_SEGUNDOS = 10


def _formatar_numero(telefone: str | None) -> str | None:
    """Mesma normalizacao ja usada no botao de WhatsApp da ficha do
    cliente (frontend/telas/ficha_cliente.py) -- so digitos, com o
    codigo do Brasil (55) na frente quando falta."""

    if not telefone:
        return None

    digitos = "".join(c for c in telefone if c.isdigit())

    if not digitos:
        return None

    if len(digitos) <= 11:
        digitos = "55" + digitos

    return digitos


class WhatsappService:

    @staticmethod
    def enviar_mensagem(db: Session, telefone: str | None, texto: str) -> bool:
        """Manda uma mensagem de texto livre via Z-API. Nunca levanta
        excecao pra fora -- uma falha aqui (credencial errada, Z-API
        fora do ar, numero invalido, integracao desligada) nao pode
        derrubar quem chamou (fechar uma venda, a checagem diaria de
        fiado parado etc.), so retorna False pra quem quiser avisar o
        usuario que o envio nao saiu."""

        try:

            config = ConfiguracaoService.buscar(db)

            if not config.whatsapp_ativo:
                return False

            if not config.whatsapp_instance_id or not config.whatsapp_token:
                return False

            numero = _formatar_numero(telefone)

            if not numero:
                return False

            url = (
                f"https://api.z-api.io/instances/{config.whatsapp_instance_id}"
                f"/token/{config.whatsapp_token}/send-text"
            )

            response = requests.post(
                url,
                json={"phone": numero, "message": texto},
                timeout=_TIMEOUT_SEGUNDOS,
            )

            return response.status_code == 200

        except Exception:
            return False

    @staticmethod
    def enviar_documento(
        db: Session,
        telefone: str | None,
        pdf_base64: str,
        nome_arquivo: str = "comprovante.pdf",
        legenda: str = "",
    ) -> tuple[bool, str | None]:
        """Manda um PDF anexado via Z-API (send-document/pdf). Ao
        contrário de enviar_mensagem, devolve o motivo da falha junto
        -- quem chama (o endpoint de comprovante) registra isso no
        histórico de envio pra quem for conferir depois o que deu
        errado."""

        try:

            config = ConfiguracaoService.buscar(db)

            if not config.whatsapp_ativo:
                return False, "Integração com WhatsApp está desligada."

            if not config.whatsapp_instance_id or not config.whatsapp_token:
                return False, "Instance ID/Token do Z-API não configurados."

            numero = _formatar_numero(telefone)

            if not numero:
                return False, "Cliente sem telefone cadastrado."

            url = (
                f"https://api.z-api.io/instances/{config.whatsapp_instance_id}"
                f"/token/{config.whatsapp_token}/send-document/pdf"
            )

            response = requests.post(
                url,
                json={
                    "phone": numero,
                    "document": f"data:application/pdf;base64,{pdf_base64}",
                    "fileName": nome_arquivo,
                    "caption": legenda,
                },
                timeout=_TIMEOUT_SEGUNDOS,
            )

            if response.status_code == 200:
                return True, None

            return False, f"Z-API retornou status {response.status_code}."

        except Exception as e:
            return False, str(e)
