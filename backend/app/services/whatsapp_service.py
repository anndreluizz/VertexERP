import os

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


_COEXY_URL = "https://api.coexy.com.br/functions/v1/meta-proxy"


def coexy_configurado() -> bool:
    """Coexy (WhatsApp oficial) entra pelo .env do servidor -- nao tem
    campo na tela de Configuracoes, o token nunca passa pelo banco nem
    pelo frontend. ponytail: env unica = uma loja; virar coluna em
    Configuracao se um dia houver varios canais."""

    return all(
        os.getenv(k)
        for k in ("COEXY_CHANNEL_TOKEN", "COEXY_PHONE_NUMBER_ID")
    )


class WhatsappService:

    @staticmethod
    def enviar_template(
        db: Session,
        telefone: str | None,
        nome_template: str,
        parametros: list[str],
        idioma: str = "pt_BR",
    ) -> bool:
        """Manda um template aprovado pelo Coexy (relay da Cloud API da
        Meta). Template e' obrigatorio pra puxar conversa: texto livre
        so passa dentro das 24h depois do cliente escrever. Mesma
        regra do enviar_mensagem: nunca levanta excecao, so False."""

        try:

            if not ConfiguracaoService.buscar(db).whatsapp_ativo:
                return False

            if not coexy_configurado():
                return False

            numero = _formatar_numero(telefone)

            if not numero:
                return False

            response = requests.post(
                f"{_COEXY_URL}/{os.environ['COEXY_PHONE_NUMBER_ID']}/messages",
                headers={
                    "Authorization": f"Bearer {os.environ['COEXY_CHANNEL_TOKEN']}"
                },
                json={
                    "messaging_product": "whatsapp",
                    "to": numero,
                    "type": "template",
                    "template": {
                        "name": nome_template,
                        "language": {"code": idioma},
                        "components": [{
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": p} for p in parametros
                            ],
                        }],
                    },
                },
                timeout=_TIMEOUT_SEGUNDOS,
            )

            return response.status_code == 200

        except Exception:
            return False

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
