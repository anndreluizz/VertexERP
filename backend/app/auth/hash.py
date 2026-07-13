from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


def gerar_hash(senha: str):
    return pwd_context.hash(senha)


def verificar_hash(
    senha: str,
    senha_hash: str
):
    return pwd_context.verify(
        senha,
        senha_hash
    )