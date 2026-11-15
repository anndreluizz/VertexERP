"""Sangria e Suprimento: valores rapidos, motivos prontos e a gaveta antes/depois."""
from PySide6.QtWidgets import QDialog

from design.privacidade import privacidade
from telas.sangria import SangriaWindow
from telas.suprimento import SuprimentoWindow


def _mostrar_valores():
    privacidade.definir_ocultos(False)


def test_sangria_mostra_a_gaveta_depois_e_quanto_fica():
    _mostrar_valores()
    j = SangriaWindow(1000.0)
    j.valor.setValue(250)
    assert j.lbl_depois.text() == "R$ 750,00"
    assert j.lbl_acao_valor.text() == "− R$ 250,00"
    assert j.lbl_legenda.text() == "75% do esperado fica na gaveta"
    assert j.lbl_depois_rotulo.text() == "DEPOIS DA SANGRIA"


def test_suprimento_soma_na_gaveta():
    _mostrar_valores()
    j = SuprimentoWindow(1000.0)
    j.valor.setValue(100)
    assert j.lbl_depois.text() == "R$ 1.100,00"
    assert j.lbl_acao_valor.text() == "+ R$ 100,00"
    assert j.lbl_depois_rotulo.text() == "DEPOIS DO SUPRIMENTO"


def test_sangria_maior_que_o_esperado_avisa_mas_nao_bloqueia():
    _mostrar_valores()
    j = SangriaWindow(100.0)
    j.valor.setValue(300)
    assert j.lbl_depois.text() == "R$ -200,00"
    assert j.lbl_legenda.text() == "Mais do que o esperado na gaveta"
    # regra de negocio intacta: confirmar so' exige valor e motivo
    j.descricao.setText("Levado ao cofre")
    j.confirmar()
    assert j.result() == QDialog.Accepted


def test_valor_rapido_e_motivo_pronto_preenchem_os_campos():
    j = SangriaWindow(500.0)
    j._chips_valor[200].click()
    assert j.valor.value() == 200
    motivos = [b for b in j.findChildren(type(j._chips_valor[200])) if b.text() == "Levado ao cofre"]
    motivos[0].click()
    assert j.dados == {"tipo": "SANGRIA", "valor": 200.0, "descricao": "Levado ao cofre"}


def test_valores_do_painel_respeitam_o_olhinho():
    privacidade.definir_ocultos(True)
    try:
        j = SangriaWindow(1000.0)
        j.valor.setValue(250)
        assert "1.000" not in j.lbl_agora.text() and "750" not in j.lbl_depois.text()
    finally:
        privacidade.definir_ocultos(True)


def test_sem_totais_so_o_formulario():
    j = SangriaWindow(None)
    assert not hasattr(j, "lbl_depois")
    j.valor.setValue(50)           # nao quebra sem o painel
    assert j.dados["valor"] == 50.0
