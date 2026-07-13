from pathlib import Path
from loguru import logger
import sys

# Cria a pasta logs automaticamente
Path("logs").mkdir(exist_ok=True)

# Remove o logger padrão
logger.remove()

# Exibe logs no terminal
logger.add(
    sys.stdout,
    level="INFO",
    colorize=True,
    format="<green>{time:DD/MM/YYYY HH:mm:ss}</green> | <level>{level}</level> | {message}"
)

# Salva logs em arquivo
logger.add(
    "logs/vertex.log",
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    level="INFO",
    encoding="utf-8"
)