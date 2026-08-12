from pydantic import BaseModel


class ConfiguracaoUpdate(BaseModel):
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


class ConfiguracaoResponse(BaseModel):
    id: int
    nome_loja: str | None
    cnpj_cpf: str | None
    endereco: str | None
    telefone: str | None
    pix_chave: str | None
    pix_nome: str | None
    pix_cidade: str | None
    logo_filename: str | None
    tem_logo: bool = False
    whatsapp_instance_id: str | None
    whatsapp_token: str | None
    whatsapp_ativo: bool
    whatsapp_lembrete_fiado_ativo: bool
    whatsapp_lembrete_fiado_dias: int
    whatsapp_comprovante_venda_ativo: bool
    smtp_host: str | None
    smtp_porta: int
    smtp_usuario: str | None
    smtp_remetente: str | None
    smtp_ativo: bool

    class Config:
        orm_mode = True
