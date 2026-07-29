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

    class Config:
        orm_mode = True
