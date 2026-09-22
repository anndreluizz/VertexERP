"""Testes da aba Backup em Configurações (Fase 6, Onda 10) --
visibilidade (admin-only) e a tabela de histórico populada a partir
do backend."""
from unittest import mock

from telas.configuracoes import Configuracoes


def _tela_configuracoes(admin=False):
    with mock.patch("telas.configuracoes.configuracoes", return_value={}), \
         mock.patch("telas.configuracoes.me", return_value={"nome": "Usuário Teste", "id": 1}), \
         mock.patch("telas.configuracoes.usuario_e_admin", return_value=admin), \
         mock.patch("services.preferencias_service.carregar", return_value={}), \
         mock.patch(
             "services.impressora_termica_service.listar_impressoras_windows",
             return_value=[],
         ), \
         mock.patch(
             "services.preferencias_service.carregar_impressora_termica",
             return_value=None,
         ):
        return Configuracoes()


def test_botao_backup_escondido_pra_quem_nao_e_admin():
    # isHidden() (nao isVisible()) de proposito -- reflete a flag
    # explicita do proprio widget, sem depender da cadeia de
    # visibilidade de um ancestral que aqui nunca foi mostrado (mesmo
    # motivo documentado em test_conectividade.py)
    tela = _tela_configuracoes(admin=False)
    assert tela.bt_backup.isHidden() is True


def test_botao_backup_visivel_pra_admin():
    tela = _tela_configuracoes(admin=True)
    assert tela.bt_backup.isHidden() is False


def test_selecionar_aba_backup_carrega_historico_uma_vez(esperar_threads):
    tela = _tela_configuracoes(admin=True)

    resposta = {
        "itens": [
            {"nome": "vertexerp_teste.sql", "tamanho_bytes": 2048,
             "criado_em": "2026-09-22T10:00:00"},
        ],
        "pasta": r"C:\Users\Teste\Documents\VertexERP\Backups",
    }

    with mock.patch(
        "telas.configuracoes.backup_service.listar_backups",
        return_value=resposta,
    ) as listar_mock:

        tela._selecionar_aba(8)
        esperar_threads(tela)

        # reabrir a aba nao deveria bater na rede de novo (so' na
        # primeira vez, ver self._backups_carregados)
        tela._selecionar_aba(0)
        tela._selecionar_aba(8)
        esperar_threads(tela)

    listar_mock.assert_called_once()
    assert tela.tabela_backups.rowCount() == 1
    assert tela.tabela_backups.item(0, 0).text() == "vertexerp_teste.sql"
    assert tela._pasta_backups_atual == resposta["pasta"]
