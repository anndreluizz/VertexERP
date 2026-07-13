from datetime import datetime


class CodeGenerator:

    @staticmethod
    def gerar(prefixo: str, numero: int):

        return f"{prefixo}{numero:06d}"