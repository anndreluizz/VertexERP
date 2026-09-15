"""Testes do cabecalho da tela de PDV (Frente de Caixa) -- por
enquanto so' a logo da loja, que so' aparece quando a loja tem logo
cadastrado (mesmo padrao de telas/configuracoes.py)."""
import base64
from unittest import mock

from telas.pdv import PDV

# PNG 1x1 transparente valido -- o menor arquivo real que da pra
# decodificar de verdade (bytes fake tipo b"abc" nao geram pixmap).
_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8A"
    "AQUBAScY42YAAAAASUVORK5CYII="
)


def _tela_pdv(tem_logo=False, logo_bytes=_PNG_1X1):
    config = {"nome_loja": "Loja Teste", "tem_logo": tem_logo}
    with mock.patch("telas.pdv.configuracoes", return_value=config):
        with mock.patch("telas.pdv.me", return_value={"id": 1}):
            with mock.patch(
                "services.preferencias_service.carregar", return_value={}
            ):
                with mock.patch(
                    "telas.pdv.comprovante_service.obter_logo_loja",
                    return_value=logo_bytes,
                ):
                    return PDV()


def test_logo_fica_escondida_quando_loja_nao_tem_logo_cadastrado():
    # isHidden() reflete o setVisible() explicito no codigo, sem
    # depender da janela-mae estar de fato na tela (isVisible() daria
    # sempre False aqui, ja que o teste nunca chama .show()).
    tela = _tela_pdv(tem_logo=False)
    assert tela.lbl_logo_pdv.isHidden() is True


def test_logo_aparece_no_cabecalho_quando_loja_tem_logo():
    tela = _tela_pdv(tem_logo=True)
    assert tela.lbl_logo_pdv.isHidden() is False
    assert not tela.lbl_logo_pdv.pixmap().isNull()


def test_logo_fica_escondida_se_loja_marca_tem_logo_mas_backend_nao_devolve_bytes():
    tela = _tela_pdv(tem_logo=True, logo_bytes=None)
    assert tela.lbl_logo_pdv.isHidden() is True
