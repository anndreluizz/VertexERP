"""Testes do login: 2FA (código por e-mail) e "Manter conectado"
(sessão lembrada via refresh_token protegido por DPAPI). Ver
services/api.py, telas/login.py, telas/verificar_2fa.py e
telas/gerenciar_usuarios.py."""
import os
import tempfile
from unittest import mock

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QWidget,
)

from services import api, preferencias_service


class _RespostaFalsa:
    def __init__(self, status_code, corpo):
        self.status_code = status_code
        self._corpo = corpo
        self.text = str(corpo)

    def json(self):
        return self._corpo


@pytest.fixture()
def configuracao_isolada(tmp_path):
    """Roda com um QSettings isolado num .ini temporário, pra nunca
    tocar na configuração real do usuário que roda os testes."""
    caminho_ini = str(tmp_path / "config_teste.ini")

    with mock.patch.object(
        preferencias_service, "_settings",
        lambda: QSettings(caminho_ini, QSettings.Format.IniFormat),
    ):
        yield


# ==================================================
# services/api.py -- login() / verificar_codigo_2fa()
# ==================================================


def test_login_sem_2fa_devolve_sucesso_direto():
    with mock.patch.object(api, "_requisitar") as requisitar_mock:
        requisitar_mock.return_value = _RespostaFalsa(200, {"access_token": "abc123"})
        ok, erro, verificacao_id = api.login("dono@loja.com", "123456")

    assert ok is True and erro is None and verificacao_id is None
    assert api.TOKEN == "abc123"


def test_login_com_2fa_pendente_devolve_verificacao_id():
    with mock.patch.object(api, "_requisitar") as requisitar_mock:
        requisitar_mock.return_value = _RespostaFalsa(
            200, {"requer_2fa": True, "verificacao_id": "verif-xyz"}
        )
        ok, erro, verificacao_id = api.login("dono@loja.com", "123456")

    assert ok is False and erro is None and verificacao_id == "verif-xyz"


def test_login_com_senha_errada_devolve_mensagem_do_backend():
    with mock.patch.object(api, "_requisitar") as requisitar_mock:
        requisitar_mock.return_value = _RespostaFalsa(401, {"detail": "Senha inválida."})
        ok, erro, verificacao_id = api.login("dono@loja.com", "errada")

    assert ok is False and erro == "Senha inválida." and verificacao_id is None


def test_verificar_codigo_2fa_com_sucesso():
    with mock.patch.object(api, "_requisitar") as requisitar_mock:
        requisitar_mock.return_value = _RespostaFalsa(200, {"access_token": "novo-token"})
        ok, erro = api.verificar_codigo_2fa("verif-xyz", "123456")

    assert ok is True and erro is None
    assert api.TOKEN == "novo-token"


def test_verificar_codigo_2fa_com_codigo_errado():
    with mock.patch.object(api, "_requisitar") as requisitar_mock:
        requisitar_mock.return_value = _RespostaFalsa(
            401, {"detail": "Código inválido ou expirado."}
        )
        ok, erro = api.verificar_codigo_2fa("verif-xyz", "000000")

    assert ok is False and "inválido" in erro


# ==================================================
# telas/verificar_2fa.py -- Verificar2FADialog
# ==================================================


def test_dialogo_2fa_constroi_e_limita_o_codigo_a_6_digitos():
    from telas.verificar_2fa import Verificar2FADialog

    dialogo = Verificar2FADialog("verif-abc", "dono@loja.com")
    assert dialogo.codigo.maxLength() == 6


def test_dialogo_2fa_confirmar_com_codigo_certo_aceita(esperar_threads):
    from telas.verificar_2fa import Verificar2FADialog

    dialogo = Verificar2FADialog("verif-abc", "dono@loja.com")

    with mock.patch("telas.verificar_2fa.verificar_codigo_2fa", return_value=(True, None)) as m:
        dialogo.codigo.setText("123456")
        dialogo.confirmar()
        esperar_threads(dialogo)

    assert dialogo.result() == QDialog.Accepted
    assert m.call_args[0] == ("verif-abc", "123456")


def test_dialogo_2fa_confirmar_com_codigo_errado_nao_aceita(esperar_threads):
    from telas.verificar_2fa import Verificar2FADialog

    dialogo = Verificar2FADialog("verif-def", "dono@loja.com")

    with mock.patch(
        "telas.verificar_2fa.verificar_codigo_2fa", return_value=(False, "Código inválido.")
    ), mock.patch.object(QMessageBox, "warning") as aviso_mock:
        dialogo.codigo.setText("000000")
        dialogo.confirmar()
        esperar_threads(dialogo)

    assert dialogo.result() != QDialog.Accepted
    assert aviso_mock.called


def test_dialogo_2fa_confirmar_com_campo_vazio_avisa_sem_chamar_api():
    from telas.verificar_2fa import Verificar2FADialog

    dialogo = Verificar2FADialog("verif-ghi", "dono@loja.com")

    with mock.patch.object(QMessageBox, "warning") as aviso_mock:
        dialogo.confirmar()

    assert aviso_mock.called


# ==================================================
# telas/login.py -- LoginWindow.entrar() roteia pro dialogo de 2FA
# e repassa o checkbox "Manter conectado"
# ==================================================


def _tela_login():
    from telas.login import LoginWindow

    tela = LoginWindow.__new__(LoginWindow)
    QWidget.__init__(tela)
    tela.usuario = QLineEdit("dono@loja.com")
    tela.senha = QLineEdit("123456")
    tela.manter_conectado = QCheckBox()
    tela.botao = QPushButton("Entrar")
    return tela


def test_login_pendente_de_2fa_abre_o_dialogo_com_verificacao_id_certo(esperar_threads):
    tela = _tela_login()

    with mock.patch("telas.login.login", return_value=(False, None, "verif-123")), \
         mock.patch("telas.login.Verificar2FADialog") as dialogo_mock, \
         mock.patch("telas.login._buscar_info_principal", return_value=({}, {})), \
         mock.patch("telas.login.PrincipalWindow") as principal_mock:

        instancia = mock.MagicMock()
        instancia.exec.return_value = QDialog.Accepted
        dialogo_mock.return_value = instancia
        dialogo_mock.Accepted = QDialog.Accepted

        tela.entrar()
        esperar_threads(tela)

    assert dialogo_mock.called
    assert dialogo_mock.call_args[0][0] == "verif-123"
    assert principal_mock.called


def test_login_2fa_cancelado_nao_abre_janela_principal(esperar_threads):
    tela = _tela_login()

    with mock.patch("telas.login.login", return_value=(False, None, "verif-456")), \
         mock.patch("telas.login.Verificar2FADialog") as dialogo_mock, \
         mock.patch("telas.login.PrincipalWindow") as principal_mock:

        instancia = mock.MagicMock()
        instancia.exec.return_value = QDialog.Rejected
        dialogo_mock.return_value = instancia
        dialogo_mock.Accepted = QDialog.Accepted

        tela.entrar()
        esperar_threads(tela)

    assert not principal_mock.called


@pytest.mark.parametrize("marcado", [True, False])
def test_login_repassa_o_estado_do_checkbox_manter_conectado(marcado, esperar_threads):
    tela = _tela_login()
    tela.manter_conectado.setChecked(marcado)

    with mock.patch("telas.login.login", return_value=(True, None, None)) as login_mock, \
         mock.patch("telas.login._buscar_info_principal", return_value=({}, {})), \
         mock.patch("telas.login.PrincipalWindow"):
        tela.entrar()
        esperar_threads(tela)

    assert login_mock.call_args.kwargs.get("lembrar") == marcado


# ==================================================
# preferencias_service -- salvar/carregar/limpar sessão (DPAPI)
# ==================================================


def test_sessao_sem_nada_salvo_devolve_none(configuracao_isolada):
    assert preferencias_service.carregar_sessao() is None


def test_sessao_salva_volta_igual_ao_carregar(configuracao_isolada):
    preferencias_service.salvar_sessao("meu-refresh-token-secreto-123")
    assert preferencias_service.carregar_sessao() == "meu-refresh-token-secreto-123"


def test_sessao_fica_criptografada_no_arquivo(configuracao_isolada, tmp_path):
    caminho_ini = preferencias_service._settings().fileName()
    preferencias_service.salvar_sessao("meu-refresh-token-secreto-123")

    with open(caminho_ini, encoding="utf-8", errors="ignore") as f:
        conteudo_bruto = f.read()

    assert "meu-refresh-token-secreto-123" not in conteudo_bruto


def test_sessao_limpar_remove_o_valor(configuracao_isolada):
    preferencias_service.salvar_sessao("refresh-qualquer")
    preferencias_service.limpar_sessao()
    assert preferencias_service.carregar_sessao() is None


# ==================================================
# services/api.py -- login()/verificar_codigo_2fa() persistindo
# quando lembrar=True, e retomar_sessao()/logout()
# ==================================================


def test_login_com_lembrar_guarda_o_refresh_token(configuracao_isolada):
    with mock.patch.object(api, "_requisitar") as requisitar_mock:
        requisitar_mock.return_value = _RespostaFalsa(
            200, {"access_token": "acesso-1", "refresh_token": "refresh-1"}
        )
        api.login("dono@loja.com", "123456", lembrar=True)

    assert preferencias_service.carregar_sessao() == "refresh-1"


def test_login_sem_lembrar_nao_guarda_nada(configuracao_isolada):
    with mock.patch.object(api, "_requisitar") as requisitar_mock:
        requisitar_mock.return_value = _RespostaFalsa(
            200, {"access_token": "acesso-2", "refresh_token": "refresh-2"}
        )
        api.login("dono@loja.com", "123456")

    assert preferencias_service.carregar_sessao() is None


def test_verificar_codigo_2fa_com_lembrar_guarda_o_refresh_token(configuracao_isolada):
    with mock.patch.object(api, "_requisitar") as requisitar_mock:
        requisitar_mock.return_value = _RespostaFalsa(
            200, {"access_token": "acesso-3", "refresh_token": "refresh-3"}
        )
        api.verificar_codigo_2fa("verif-x", "123456", lembrar=True)

    assert preferencias_service.carregar_sessao() == "refresh-3"


def test_retomar_sessao_sem_nada_guardado(configuracao_isolada):
    assert api.retomar_sessao() is False


def test_retomar_sessao_com_refresh_valido(configuracao_isolada):
    preferencias_service.salvar_sessao("refresh-guardado")
    api.TOKEN = None

    with mock.patch.object(api, "_requisitar") as requisitar_mock:
        requisitar_mock.return_value = _RespostaFalsa(200, {"access_token": "token-renovado"})
        resultado = api.retomar_sessao()

    assert resultado is True
    assert api.TOKEN == "token-renovado"
    assert requisitar_mock.call_args.kwargs["json"] == {"refresh_token": "refresh-guardado"}


def test_retomar_sessao_com_refresh_invalido_limpa_a_sessao(configuracao_isolada):
    preferencias_service.salvar_sessao("refresh-invalido")

    with mock.patch.object(api, "_requisitar") as requisitar_mock:
        requisitar_mock.return_value = _RespostaFalsa(401, {"detail": "Sessão expirada."})
        resultado = api.retomar_sessao()

    assert resultado is False
    assert preferencias_service.carregar_sessao() is None


def test_retomar_sessao_com_erro_de_rede_nao_trava(configuracao_isolada):
    preferencias_service.salvar_sessao("refresh-qualquer")

    with mock.patch.object(api, "_requisitar", side_effect=Exception("sem rede")):
        assert api.retomar_sessao() is False


def test_logout_limpa_token_e_sessao_guardada(configuracao_isolada):
    preferencias_service.salvar_sessao("refresh-pra-ser-limpo")
    api.TOKEN = "algum-token"

    api.logout()

    assert api.TOKEN is None
    assert preferencias_service.carregar_sessao() is None


# ==================================================
# telas/gerenciar_usuarios.py -- toggle de 2FA por usuário
# ==================================================


def test_alternar_2fa_liga_pra_usuario_desativado(esperar_threads):
    from telas.gerenciar_usuarios import GerenciarUsuariosDialog

    tela = GerenciarUsuariosDialog.__new__(GerenciarUsuariosDialog)
    QDialog.__init__(tela)
    tela.usuarios = [
        {"id": 1, "nome": "Fulano", "email": "fulano@loja.com", "ativo": True,
         "admin": False, "dois_fatores_ativo": False},
    ]
    tela.tabela = QTableWidget(1, 3)
    tela.tabela.setCurrentCell(0, 0)
    # painel do usuário selecionado (habilita/desabilita durante a ação)
    tela.painel_conteudo = QWidget()
    tela._carregando = False

    with mock.patch("telas.gerenciar_usuarios.atualizar_usuario") as atualizar_mock, \
         mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes), \
         mock.patch.object(GerenciarUsuariosDialog, "carregar") as carregar_mock:

        atualizar_mock.return_value = _RespostaFalsa(200, {})
        tela.alternar_2fa()
        esperar_threads(tela)

    assert atualizar_mock.call_args[0][1] == {"dois_fatores_ativo": True}
    assert carregar_mock.called
