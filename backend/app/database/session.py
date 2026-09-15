from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

import os

load_dotenv()

DATABASE_URL = (
    f"postgresql+psycopg://"
    f"{os.getenv('DB_USER')}:"
    f"{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:"
    f"{os.getenv('DB_PORT')}/"
    f"{os.getenv('DB_NAME')}"
)

# echo=True loga o texto INTEIRO de toda consulta SQL -- ótimo pra
# depurar em dev, mas em produção isso significa uma escrita em disco
# (sem buffer, feita na hora, ver backend_entry.py: buffering=1) a
# cada tela que carrega dado, pra sempre, com o arquivo de log só
# crescendo sem limite -- causa real de lentidão geral que piora com
# o tempo (escrita num arquivo de log gigante fica mais pesada, ainda
# mais com antivírus escaneando em tempo real). So liga com
# DEBUG=True no .env (que só existe em ambiente de desenvolvimento --
# o .env gerado pelo launcher.py pra instalação de verdade não tem
# essa linha, então cai pra False sozinho).
engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("DEBUG", "False") == "True"
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()