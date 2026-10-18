
from app.schemas.base import Schema


class ConfiguracaoUpdate(Schema):
    nome_loja: str | None = None
    cnpj_cpf: str | None = None
    endereco: str | None = None
    telefone: str | None = None
    pix_chave: str | None = None
    pix_nome: str | None = None
    pix_cidade: str | None = None
    logo_filename: str | None = None
    # imagem em base64 (entrada apenas); None mantem o logo atual --
    # mesmo padrao de Cliente.foto_base64
    logo_base64: str | None = None
    whatsapp_instance_id: str | None = None
    whatsapp_token: str | None = None
    whatsapp_ativo: bool | None = None
    whatsapp_lembrete_fiado_ativo: bool | None = None
    whatsapp_lembrete_fiado_dias: int | None = None
    whatsapp_comprovante_venda_ativo: bool | None = None
    smtp_host: str | None = None
    smtp_porta: int | None = None
    smtp_usuario: str | None = None
    smtp_senha: str | None = None
    smtp_remetente: str | None = None
    smtp_ativo: bool | None = None


class ConfiguracaoResponse(Schema):
    id: int
    nome_loja: str | None = None
    cnpj_cpf: str | None = None
    endereco: str | None = None
    telefone: str | None = None
    pix_chave: str | None = None
    pix_nome: str | None = None
    pix_cidade: str | None = None
    logo_filename: str | None = None
    tem_logo: bool = False
    whatsapp_instance_id: str | None = None
    # whatsapp_token nao volta aqui por segurança -- e' a credencial
    # que autentica direto na Z-API (quem tiver o valor consegue
    # mandar mensagem como se fosse a loja), mesmo criterio ja usado
    # pro smtp_senha. Qualquer usuario autenticado pode chamar esse
    # GET (a tela principal e a ficha do cliente usam pra pegar
    # nome/logo/pix), entao o token nunca deve estar na resposta.
    whatsapp_ativo: bool
    whatsapp_lembrete_fiado_ativo: bool
    whatsapp_lembrete_fiado_dias: int
    whatsapp_comprovante_venda_ativo: bool
    smtp_host: str | None = None
    smtp_porta: int
    smtp_usuario: str | None = None
    smtp_remetente: str | None = None
    smtp_ativo: bool
