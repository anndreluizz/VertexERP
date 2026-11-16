"""Cadastro em etapas: o assistente preenche o diálogo original e manda salvar."""
import importlib
import pkgutil
from unittest import mock

from PySide6.QtWidgets import QDialog

from telas import cadastro_produto as pacote


def _sem_rede(monkeypatch):
    for m in pkgutil.iter_modules(pacote.__path__):
        modulo = importlib.import_module(f"telas.cadastro_produto.{m.name}")
        if hasattr(modulo, "rodar_em_thread"):
            monkeypatch.setattr(modulo, "rodar_em_thread", lambda *a, **k: None)
    for nome in ("telas.cadastro_cliente", "telas.cadastro_despesa"):
        modulo = importlib.import_module(nome)
        monkeypatch.setattr(modulo, "rodar_em_thread", lambda *a, **k: None)


def test_produto_em_etapas_preenche_o_cadastro_e_aceita(_qapp, monkeypatch):
    _sem_rede(monkeypatch)
    from telas.cadastros_etapas import novo_produto_assistente

    with mock.patch("services.preferencias_service.carregar", return_value={}):
        a = novo_produto_assistente()

    # etapa 1: sem nome não passa, e o erro é do campo do nome
    a.avancar()
    assert a._i == 0 and a._campos[1].erro.isVisibleTo(a)
    assert not a._campos[0].erro.isVisibleTo(a)
    a._campos[1].w.setText("Mochila preta")
    a.avancar()
    # etapa 2: preço obrigatório
    a._campos[1].w.setValue(129.9)
    a.avancar()
    # etapa 3 (opcional) e revisão
    a.avancar()
    assert a._passos[a._i].get("revisao")

    aceito = []
    a.accepted.connect(lambda: aceito.append(True))
    a.avancar()  # Cadastrar produto

    assert aceito and a.result() == QDialog.Accepted
    # o que o chamador lê vem do cadastro original
    assert a.dados["nome"] == "MOCHILA PRETA" and a.dados["preco_venda"] == 129.9


def test_cliente_em_etapas_so_o_nome_e_obrigatorio(_qapp, monkeypatch):
    _sem_rede(monkeypatch)
    from telas import cadastro_cliente
    from telas.cadastros_etapas import novo_cliente_assistente

    salvou = []
    monkeypatch.setattr(
        cadastro_cliente.CadastroClienteDialog, "salvar",
        lambda s: salvou.append((s.nome.text(), s.limite_credito.text())),
    )
    a = novo_cliente_assistente()

    a.avancar()
    assert a._i == 0 and a._campos[0].erro.isVisibleTo(a)
    a._campos[0].w.setText("Maria")
    a._campos[1].w.setText("65999123045")
    assert a._campos[1].w.text() == "(65) 99912-3045"  # formata sozinho
    a.avancar()
    a.avancar()  # documentos e e-mail em branco passam
    # o limite é obrigatório e já vem sugerido (R$ 200); zerado não passa
    assert not a.bt_pular.isVisibleTo(a) or a._passos[a._i].get("opcional") is None
    a._campos[0].w.setValue(0)
    a.avancar()
    assert a._i == 2 and a._campos[0].erro.isVisibleTo(a)
    a._campos[0].w.setValue(300)
    a.avancar()  # revisão
    a.avancar()  # Cadastrar cliente
    assert salvou == [("MARIA", "300,00")]  # o cadastro original grava o nome em maiúsculas


def test_cliente_erro_so_no_campo_errado(_qapp, monkeypatch):
    _sem_rede(monkeypatch)
    from telas.cadastros_etapas import novo_cliente_assistente

    a = novo_cliente_assistente()
    a._campos[0].w.setText("Maria")
    a._campos[1].w.setText("123")  # WhatsApp incompleto
    a.avancar()
    assert a._i == 0
    assert a._campos[1].erro.isVisibleTo(a) and not a._campos[0].erro.isVisibleTo(a)
    a._campos[1].w.setText("")
    assert not a._campos[1].erro.isVisibleTo(a)


def test_enter_vai_pro_proximo_campo_e_so_no_ultimo_avanca(_qapp, monkeypatch):
    _sem_rede(monkeypatch)
    from telas.cadastros_etapas import novo_cliente_assistente

    a = novo_cliente_assistente()
    a.show()
    a._campos[0].w.setText("Maria")
    a._campos[0].w.setFocus()
    a.enter()
    assert a._i == 0 and a.focusWidget() is a._campos[1].w
    a.enter()  # último campo da etapa: avança
    assert a._i == 1


def test_boleto_em_etapas_preenche_o_cadastro(_qapp, monkeypatch):
    _sem_rede(monkeypatch)
    from telas import cadastro_despesa
    from telas.cadastros_etapas import nova_despesa_assistente

    visto = {}

    def salvar(self):
        visto.update(
            descricao=self.descricao.text(), valor=self.valor.text(),
            repeticao=self.repeticao.currentData(), parcelas=self.parcelas.value(),
        )

    monkeypatch.setattr(cadastro_despesa.CadastroDespesaDialog, "salvar", salvar)
    a = nova_despesa_assistente()
    a._campos[1].w.setText("Energia")
    a.avancar()
    a._campos[0].w.setValue(612)
    a.avancar()
    from design.assistente import Opcoes
    a._campos[0].w.findChild(Opcoes).marcar(1)  # Parcelado
    a.avancar()
    a.avancar()  # Cadastrar boleto
    assert visto["descricao"] == "Energia" and visto["valor"] == "612,00"
    assert visto["repeticao"] == "PARCELADO"


def test_usuario_em_etapas_valida_senha_e_preenche_o_cadastro(_qapp, monkeypatch):
    _sem_rede(monkeypatch)
    from telas import gerenciar_usuarios
    from telas.cadastros_etapas import novo_usuario_assistente

    visto = []
    monkeypatch.setattr(gerenciar_usuarios.NovoUsuarioDialog, "criar", lambda s: visto.append((s.nome.text(), s.email.text(), s.senha.text())))
    a = novo_usuario_assistente([{"id": 3, "nome": "Gerente"}])

    a._campos[0].w.setText("Maria")
    a._campos[1].w.setText("maria@loja.com")
    a.avancar()
    # senha curta: erro só na senha
    a._campos[0].w.setText("123")
    a._campos[1].w.setText("123")
    a.avancar()
    assert a._i == 1 and a._campos[0].erro.isVisibleTo(a) and not a._campos[1].erro.isVisibleTo(a)
    a._campos[0].w.setText("segredo1")
    a._campos[1].w.setText("outra123")  # não confere
    a.avancar()
    assert a._i == 1 and a._campos[1].erro.isVisibleTo(a)
    a._campos[1].w.setText("segredo1")
    a.avancar()
    a.avancar()  # perfil
    a.avancar()  # Cadastrar usuário
    assert visto == [("MARIA", "maria@loja.com", "segredo1")] or visto[0][1:] == ("maria@loja.com", "segredo1")


def test_fornecedor_em_etapas_valida_cnpj_e_preenche_o_cadastro(_qapp, monkeypatch):
    _sem_rede(monkeypatch)
    from telas import cadastro_fornecedor
    from telas.cadastros_etapas import novo_fornecedor_assistente

    visto = []
    monkeypatch.setattr(
        cadastro_fornecedor.CadastroFornecedorDialog, "salvar",
        lambda s: visto.append((s.razao_social.text(), s.cnpj.text(), s.margem_padrao.value())),
    )
    a = novo_fornecedor_assistente()
    a.avancar()  # sem razão social: erro só nela
    assert a._i == 0 and a._campos[0].erro.isVisibleTo(a) and not a._campos[1].erro.isVisibleTo(a)
    a._campos[0].w.setText("Distribuidora Central Ltda")
    a.avancar()
    a._campos[0].w.setText("123")  # CNPJ incompleto
    a.avancar()
    assert a._i == 1 and a._campos[0].erro.isVisibleTo(a)
    a._campos[0].w.setText("11222333000181")
    a.avancar()
    a.avancar()  # contato (opcional)
    a._campos[1].w.setValue(30)
    a.avancar()  # compras
    a.avancar()  # Cadastrar fornecedor
    assert visto and visto[0][0] == "DISTRIBUIDORA CENTRAL LTDA" and visto[0][2] == 30


def test_categoria_em_etapas_cria_pelo_servico_e_guarda_o_nome(_qapp, monkeypatch):
    from design import assistente as modulo
    from telas.cadastros_etapas import nova_categoria_assistente

    chamadas = []

    def falso(parent, func, *args, ao_sucesso=None, ao_erro=None, ao_finalizar=None):
        # o contrato real: retornos são métodos de um QObject, não funções soltas
        assert all(getattr(cb, "__self__", None) is not None for cb in (ao_sucesso, ao_erro))
        chamadas.append(args)
        resposta = mock.Mock(status_code=201)
        ao_sucesso((resposta, args[0]))

    monkeypatch.setattr(modulo, "rodar_em_thread", falso)
    a = nova_categoria_assistente()
    a._campos[0].w.setText("papelaria")
    a._campos[1].w.setText("canetas e cadernos")
    a.avancar()
    a.avancar()  # Criar categoria
    assert chamadas == [("PAPELARIA", "canetas e cadernos")]
    assert a.nome_criado == "PAPELARIA" and a.result() == QDialog.Accepted
