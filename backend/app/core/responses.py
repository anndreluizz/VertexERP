from typing import Any


class ApiResponse:

    @staticmethod
    def success(data: Any = None, message: str = "Operação realizada com sucesso."):
        return {
            "success": True,
            "message": message,
            "data": data
        }

    @staticmethod
    def error(message: str):
        return {
            "success": False,
            "message": message,
            "data": None
        }