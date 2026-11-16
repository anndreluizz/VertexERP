from design.seletor import Seletor


def _seletor(_qapp, campo=False):
    s = Seletor(campo=campo)
    s.addItem("Todas", None)
    for i in range(10):
        s.addItem(f"Loja {i}", i)
    return s


def test_menu_escolhe_item_e_avisa(_qapp):
    s = _seletor(_qapp)
    s.show()
    avisos = []
    s.activated.connect(avisos.append)
    s.showPopup()
    menu = s.findChild(type(s.findChild(object, "menuSeletor")), "menuSeletor")
    menu._botoes[3].click()
    assert s.currentData() == 2 and avisos == [3]
    assert s._ativo()  # fora do padrao (Todas) -> pilula azul


def test_filtro_ignora_estilo_da_tela_e_campo_aceita(_qapp):
    f, c = _seletor(_qapp), _seletor(_qapp, campo=True)
    antes = f.styleSheet()
    f.setStyleSheet("QComboBox { color: red; }")
    c.setStyleSheet("QComboBox { color: red; }")
    assert f.styleSheet() == antes and "red" in c.styleSheet()


def test_engrenagem_do_header_so_para_admin(_qapp):
    from unittest import mock
    from design import header as h
    with mock.patch.object(h.Header, "_atualizar_contagem_notificacoes"), \
         mock.patch.object(h.Header, "_atualizar_contagem_aprovacoes"):
        admin = h.Header("Loja", "Ana", "Admin", admin=True, na_barra=True)
        vend = h.Header("Loja", "Bia", "Vendedor", admin=False, na_barra=True)
        admin.show(); vend.show()
        avisos = []
        admin.solicitou_configuracoes.connect(lambda: avisos.append(1))
        admin.bt_config.click()
        assert avisos == [1] and admin.bt_config.isVisible() and not vend.bt_config.isVisible()
