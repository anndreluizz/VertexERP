from fastapi import HTTPException


class VertexException(HTTPException):

    def __init__(self, status_code: int, detail: str):
        super().__init__(
            status_code=status_code,
            detail=detail
        )


class UsuarioNaoEncontrado(VertexException):

    def __init__(self):
        super().__init__(
            status_code=404,
            detail="Usuário não encontrado."
        )


class EmailJaCadastrado(VertexException):

    def __init__(self):
        super().__init__(
            status_code=400,
            detail="E-mail já cadastrado."
        )


class SenhaInvalida(VertexException):

    def __init__(self):
        super().__init__(
            status_code=401,
            detail="Senha inválida."
        )


class TokenInvalido(VertexException):

    def __init__(self):
        super().__init__(
            status_code=401,
            detail="Token inválido."
        )


class SemPermissao(VertexException):

    def __init__(self):
        super().__init__(
            status_code=403,
            detail="Você não possui permissão."
        )