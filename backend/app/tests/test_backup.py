import json
import os
from datetime import datetime, timedelta
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
            arquivo.write(
                "-- dump fake\n--\n-- PostgreSQL database dump complete\n--\n"
            )
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
    assert not list(tmp_path.glob("*.tmp"))


def test_criar_manual_descarta_dump_truncado(tmp_path):
    # pg_dump "terminou" mas o arquivo nao tem o rodape -- nao pode
    # sobrar nenhum .sql com cara de backup bom na pasta

    def _pg_dump_truncado(comando, **kwargs):
        caminho_saida = comando[comando.index("-f") + 1]
        with open(caminho_saida, "w", encoding="utf-8") as arquivo:
            arquivo.write("-- dump cortado no meio\nCOPY public.vendas")
        return mock.Mock(returncode=0, stderr="")

    with mock.patch(
        "app.services.backup_service._pasta_backups", return_value=str(tmp_path)
    ), mock.patch(
        "app.services.backup_service._caminho_pg_dump", return_value="pg_dump"
    ), mock.patch("subprocess.run", side_effect=_pg_dump_truncado):
        try:
            BackupService.criar_manual()
            assert False, "deveria ter levantado excecao"
        except Exception as erro:
            assert "incompleto" in str(erro)

    assert not list(tmp_path.iterdir())


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


def _item(horas_atras, agora):
    return {
        "nome": "vertexerp_x.sql",
        "tamanho_bytes": 1,
        "criado_em": agora - timedelta(hours=horas_atras),
    }


def test_alerta_quando_ultimo_backup_automatico_falhou():
    agora = datetime(2026, 9, 26, 12, 0)
    status = {"erro": "pg_dump falhou: disco cheio", "copia_externa": None}

    alerta = BackupService.alerta([_item(1, agora)], status, agora)

    assert "falhou" in alerta
    assert "disco cheio" in alerta


def test_alerta_quando_nao_ha_nenhum_backup():
    assert "Nenhum backup" in BackupService.alerta([], None)


def test_alerta_quando_backup_parou_ha_mais_de_24h():
    agora = datetime(2026, 9, 26, 12, 0)
    status = {"erro": None, "copia_externa": "C:\OneDrive\Backups"}

    alerta = BackupService.alerta([_item(50, agora)], status, agora)

    assert "2 dia(s)" in alerta


def test_alerta_quando_backup_fica_so_neste_pc():
    agora = datetime(2026, 9, 26, 12, 0)
    status = {"erro": None, "copia_externa": None, "erro_copia_externa": None}

    alerta = BackupService.alerta([_item(1, agora)], status, agora)

    assert "só neste PC" in alerta
    assert "VERTEXERP_BACKUP_EXTRA" in alerta


def test_alerta_quando_copia_externa_falhou():
    agora = datetime(2026, 9, 26, 12, 0)
    status = {
        "erro": None,
        "copia_externa": "C:\OneDrive\Backups",
        "erro_copia_externa": "Acesso negado",
    }

    alerta = BackupService.alerta([_item(1, agora)], status, agora)

    assert "C:\OneDrive\Backups" in alerta
    assert "Acesso negado" in alerta


def test_sem_alerta_quando_backup_recente_e_copiado_pra_fora():
    agora = datetime(2026, 9, 26, 12, 0)
    status = {
        "erro": None,
        "copia_externa": "C:\OneDrive\Backups",
        "erro_copia_externa": None,
    }

    assert BackupService.alerta([_item(3, agora)], status, agora) is None


def test_sem_status_do_launcher_so_alerta_backup_atrasado():
    # backend rodando sem o launcher (dev): sem status_backup.json nao
    # da' pra saber da copia externa, entao nao reclama dela
    agora = datetime(2026, 9, 26, 12, 0)

    assert BackupService.alerta([_item(3, agora)], None, agora) is None


def test_rota_backup_devolve_alerta_e_copia_externa_do_status(
    client, auth_headers, tmp_path
):
    (tmp_path / "vertexerp_teste.sql").write_text("x")
    (tmp_path / "status_backup.json").write_text(
        json.dumps({
            "tentativa_em": "2026-09-26T10:00:00",
            "erro": None,
            "copia_externa": None,
            "erro_copia_externa": None,
        }),
        encoding="utf-8",
    )

    with mock.patch(
        "app.services.backup_service._pasta_backups", return_value=str(tmp_path)
    ):
        response = client.get("/backup/", headers=auth_headers)

    assert response.status_code == 200
    corpo = response.json()
    assert corpo["copia_externa"] is None
    assert "só neste PC" in corpo["alerta"]
    assert [i["nome"] for i in corpo["itens"]] == ["vertexerp_teste.sql"]


def test_aviso_de_backup_no_celular_nao_repete_o_mesmo_alerta_toda_hora():
    from app.services.backup_service import deve_avisar

    agora = datetime(2026, 9, 26, 12, 0)
    falhou = "O último backup automático falhou: disco cheio"

    assert deve_avisar(falhou, None, None, agora)
    assert not deve_avisar(falhou, falhou, agora - timedelta(hours=1), agora)
    assert deve_avisar(falhou, falhou, agora - timedelta(hours=25), agora)
    # alerta mudou: avisa na hora
    assert deve_avisar("Nenhum backup", falhou, agora - timedelta(hours=1), agora)
    # tudo certo: nada
    assert not deve_avisar(None, falhou, agora, agora)
