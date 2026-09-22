import os
from datetime import datetime
from unittest import mock

from app.services.backup_service import BackupService


def test_listar_ignora_arquivos_que_nao_sao_sql(tmp_path):
    (tmp_path / "vertexerp_2026-09-01_100000.sql").write_text("x")
    (tmp_path / "nao_e_backup.txt").write_text("x")

    with mock.patch(
        "app.services.backup_service._pasta_backups", return_value=str(tmp_path)
    ):
        itens = BackupService.listar()

    nomes = [i["nome"] for i in itens]
    assert nomes == ["vertexerp_2026-09-01_100000.sql"]


def test_listar_ordena_mais_recente_primeiro(tmp_path):
    antigo = tmp_path / "vertexerp_antigo.sql"
    novo = tmp_path / "vertexerp_novo.sql"
    antigo.write_text("x")
    novo.write_text("x")

    agora = datetime.now().timestamp()
    os.utime(antigo, (agora - 100, agora - 100))
    os.utime(novo, (agora, agora))

    with mock.patch(
        "app.services.backup_service._pasta_backups", return_value=str(tmp_path)
    ):
        itens = BackupService.listar()

    assert [i["nome"] for i in itens] == ["vertexerp_novo.sql", "vertexerp_antigo.sql"]


def test_criar_manual_chama_pg_dump_e_devolve_info_do_arquivo(tmp_path):

    def _pg_dump_fake(comando, **kwargs):
        caminho_saida = comando[comando.index("-f") + 1]
        with open(caminho_saida, "w", encoding="utf-8") as arquivo:
            arquivo.write("-- dump fake")
        return mock.Mock(returncode=0, stderr="")

    with mock.patch(
        "app.services.backup_service._pasta_backups", return_value=str(tmp_path)
    ), mock.patch(
        "app.services.backup_service._caminho_pg_dump", return_value="pg_dump"
    ), mock.patch("subprocess.run", side_effect=_pg_dump_fake):

        resultado = BackupService.criar_manual()

    assert resultado["nome"].startswith("vertexerp_")
    assert resultado["nome"].endswith(".sql")
    assert resultado["tamanho_bytes"] > 0
    assert (tmp_path / resultado["nome"]).exists()


def test_criar_manual_levanta_excecao_se_pg_dump_falhar(tmp_path):

    with mock.patch(
        "app.services.backup_service._pasta_backups", return_value=str(tmp_path)
    ), mock.patch(
        "app.services.backup_service._caminho_pg_dump", return_value="pg_dump"
    ), mock.patch(
        "subprocess.run",
        return_value=mock.Mock(returncode=1, stderr="erro de conexao"),
    ):
        try:
            BackupService.criar_manual()
            assert False, "deveria ter levantado excecao"
        except Exception as erro:
            assert "erro de conexao" in str(erro)


def test_rota_backup_exige_admin(client, auth_headers_comum):
    response = client.get("/backup/", headers=auth_headers_comum)
    assert response.status_code == 403


def test_rota_backup_lista_pra_admin(client, auth_headers, tmp_path):
    (tmp_path / "vertexerp_teste.sql").write_text("x")

    with mock.patch(
        "app.services.backup_service._pasta_backups", return_value=str(tmp_path)
    ):
        response = client.get("/backup/", headers=auth_headers)

    assert response.status_code == 200
    nomes = [i["nome"] for i in response.json()["itens"]]
    assert "vertexerp_teste.sql" in nomes
