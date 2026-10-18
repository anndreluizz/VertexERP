from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    APP_NAME: str = "Vertex ERP"

    APP_VERSION: str = "1.0.0"

    DB_HOST: str

    DB_PORT: int

    DB_NAME: str

    DB_USER: str

    DB_PASSWORD: str

    SECRET_KEY: str

    JWT_ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    DEBUG: bool = True

    class Config:
        env_file = ".env"


settings = Settings()