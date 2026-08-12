from pydantic import BaseModel


class ConfiguracaoUpdate(BaseModel):
    nome_loja: str | None = None
    cnpj_cpf: str | None = None
    endereco: str | None = None
    telefone: str | None = None
    pix_chave: str | None = None
    pix_nome: str | None = None
    pix_cidade: str | None = None
    impressao_comprovante: str | None = None


class ConfiguracaoResponse(BaseModel):
    id: int
    nome_loja: str | None = None
    cnpj_cpf: str | None = None
    endereco: str | None = None
    telefone: str | None = None
    pix_chave: str | None = None
    pix_nome: str | None = None
    pix_cidade: str | None = None
    logo_filename: str | None = None
    impressao_comprovante: str | None = None

    class Config:
        orm_mode = True
