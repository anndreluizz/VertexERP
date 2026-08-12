import os

# Precisa ser definido antes de importar qualquer módulo de app/, pois
# app/database/session.py monta a DATABASE_URL a partir do ambiente
# assim que é importado (e load_dotenv não sobrescreve o que já existe).
os.environ.setdefault("DB_NAME", "vertexerp_test")

import psycopg
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.session import DATABASE_URL
from app.auth.hash import gerar_hash

# Garante que todos os models estejam registrados em Base.metadata
# antes do create_all/drop_all (mesmo motivo do import manual em
# migrations/env.py).
from app.models import (  # noqa: F401
    caixa,
    categoria,
    cliente,
    compra,
    configuracao,
    conta_pagar,
    conta_receber,
    fornecedor,
    item_compra,
    item_venda,
    movimento_caixa,
    movimento_estoque,
    movimento_fiado,
    produto,
    user,
    venda,
)

import main as app_main

from app.api.v1 import (
    auth as auth_router,
    users as users_router,
    dashboard as dashboard_router,
    clientes as clientes_router,
    categorias as categorias_router,
    produtos as produtos_router,
    fornecedores as fornecedores_router,
    compras as compras_router,
    vendas as vendas_router,
    caixa as caixa_router,
    movimento_caixa as movimento_caixa_router,
    contas_receber as contas_receber_router,
    contas_pagar as contas_pagar_router,
    pdv as pdv_router,
    estoque as estoque_router,
    financeiro as financeiro_router,
    fiado as fiado_router,
    configuracoes as configuracoes_router,
    relatorios as relatorios_router,
)
from app.auth import dependencies as auth_dependencies

# Cada router (e app/auth/dependencies.py) define seu próprio get_db()
# local, então o override do FastAPI precisa ser aplicado em cada um.
MODULOS_COM_GET_DB = [
    auth_router,
    users_router,
    dashboard_router,
    clientes_router,
    categorias_router,
    produtos_router,
    fornecedores_router,
    compras_router,
    vendas_router,
    caixa_router,
    movimento_caixa_router,
    contas_receber_router,
    contas_pagar_router,
    pdv_router,
    estoque_router,
    financeiro_router,
    fiado_router,
    configuracoes_router,
    relatorios_router,
    auth_dependencies,
]

TEST_ENGINE = sa.create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(
    bind=TEST_ENGINE,
    autoflush=False,
    autocommit=False,
)


def _criar_banco_teste():
    nome_banco = os.environ["DB_NAME"]

    conn = psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname="postgres",
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        autocommit=True,
    )

    try:
        conn.execute(f'CREATE DATABASE "{nome_banco}"')
    except psycopg.errors.DuplicateDatabase:
        pass
    finally:
        conn.close()


@pytest.fixture(scope="session", autouse=True)
def _configurar_banco_teste():
    _criar_banco_teste()
    # DROP SCHEMA (em vez de Base.metadata.drop_all) garante que o banco de
    # teste fica limpo mesmo com tabelas órfãs que não estão nos models
    # atuais — ex.: sobras de uma feature em desenvolvimento numa sessão
    # paralela, que Base.metadata.drop_all não sabe remover e quebra com
    # "DependentObjectsStillExist" na primeira FK cruzada.
    with TEST_ENGINE.begin() as conn:
        conn.execute(sa.text("DROP SCHEMA public CASCADE"))
        conn.execute(sa.text("CREATE SCHEMA public"))
    Base.metadata.create_all(TEST_ENGINE)
    yield
    TEST_ENGINE.dispose()


@pytest.fixture(autouse=True)
def _limpar_tabelas():
    with TEST_ENGINE.begin() as conn:
        tabelas = ", ".join(
            f'"{tabela.name}"' for tabela in reversed(Base.metadata.sorted_tables)
        )
        conn.execute(sa.text(f"TRUNCATE TABLE {tabelas} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture()
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    def _override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    for modulo in MODULOS_COM_GET_DB:
        app_main.app.dependency_overrides[modulo.get_db] = _override_get_db

    # raise_server_exceptions=False: erros de negócio (raise Exception nos
    # services) são convertidos em 400 pelo handler global do main.py, mas
    # o TestClient por padrão re-levanta a exceção original mesmo assim.
    # Isso faz o client se comportar como um cliente HTTP real.
    with TestClient(
        app_main.app,
        raise_server_exceptions=False,
    ) as test_client:
        yield test_client

    app_main.app.dependency_overrides.clear()


# ==========================================
# DADOS DE APOIO REUTILIZÁVEIS
# ==========================================

@pytest.fixture()
def usuario(db):
    from app.models.user import User

    novo = User(
        nome="Usuário Teste",
        email="teste@vertex.com",
        senha=gerar_hash("123456"),
        ativo=True,
        admin=True,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


@pytest.fixture()
def auth_headers(client, usuario):
    response = client.post(
        "/auth/login",
        json={"email": usuario.email, "senha": "123456"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def usuario_comum(db):
    from app.models.user import User

    novo = User(
        nome="Usuário Comum",
        email="comum@vertex.com",
        senha=gerar_hash("123456"),
        ativo=True,
        admin=False,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


@pytest.fixture()
def auth_headers_comum(client, usuario_comum):
    response = client.post(
        "/auth/login",
        json={"email": usuario_comum.email, "senha": "123456"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def produto(db):
    from app.models.produto import Produto

    novo = Produto(
        codigo="P001",
        nome="Produto Teste",
        descricao="Produto usado nos testes automatizados",
        categoria="Geral",
        unidade="UN",
        preco_custo=10.0,
        preco_venda=20.0,
        estoque=50,
        estoque_minimo=5,
        ativo=True,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


@pytest.fixture()
def cliente(db):
    from app.models.cliente import Cliente

    novo = Cliente(
        nome="Cliente Teste",
        cpf_cnpj="12345678900",
        email="cliente@teste.com",
        telefone="11999999999",
        ativo=True,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


@pytest.fixture()
def fornecedor(db):
    from app.models.fornecedor import Fornecedor

    novo = Fornecedor(
        razao_social="Fornecedor Teste LTDA",
        nome_fantasia="Fornecedor Teste",
        cnpj="12345678000199",
        ativo=True,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


@pytest.fixture()
def caixa_aberto(db):
    from app.models.caixa import Caixa

    novo = Caixa(
        saldo_inicial=100.0,
        saldo_final=100.0,
        status="ABERTO",
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo
