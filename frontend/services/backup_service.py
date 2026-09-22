from services.api import get, post


def listar_backups():

    response = get("/backup/")

    if response.status_code != 200:
        raise Exception(
            f"Falha ao carregar o histórico de backups "
            f"(HTTP {response.status_code}): {response.text}"
        )

    return response.json()


def criar_backup_manual():
    return post("/backup/manual", {})
