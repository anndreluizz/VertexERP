"""Cadastro de cliente, produto e conta a pagar em etapas.

Cada função devolve um AssistenteDialogo que se usa como o diálogo de
cadastro de sempre (`.exec()`, depois lê `cliente_salvo`/`dados`): por trás
dele há o diálogo de cadastro original, que é preenchido no fim e salva.
Editar continua abrindo o diálogo completo."""

from PySide6.QtCore import QDate, QTimer

from design.assistente import (
    AssistenteDialogo, CampoEtapa, Contador, DataRapida, Escolha, Opcoes,
    ValoresRapidos, campo_dinheiro,
)
from design.widgets import CampoTexto
from services.worker import rodar_em_thread
from utils.formatacao import formatar_moeda
from utils.validacao import email_valido
from widgets.fields.cpf_field import CpfCnpjField
from widgets.fields.email_field import EmailField
from widgets.fields.phone_field import PhoneField


def _digitos(texto):
    return "".join(c for c in texto if c.isdigit())


def _decimal_br(valor):
    return f"{valor:.2f}".replace(".", ",")


def _itens(combo):
    """Itens de um combo (sem o 'Todas'/vazio do começo)."""
    textos = [combo.itemText(i) for i in range(combo.count())]
    return [t for t in textos if t and not t.lower().startswith(("todas", "selecione", "sem "))]


# ----------------------------------------------------------------------
# CLIENTE
# ----------------------------------------------------------------------

def novo_cliente_assistente(parent=None):
    from telas.cadastro_cliente import CadastroClienteDialog

    interno = CadastroClienteDialog(parent=parent)
    campos = {}

    def etapa_contato():
        campos["nome"] = CampoTexto("Ex.: Maria das Graças")
        campos["whatsapp"] = PhoneField()
        return [
            CampoEtapa("Nome do cliente", campos["nome"], obrigatorio=True),
            CampoEtapa(
                "WhatsApp", campos["whatsapp"],
                valida=lambda w: None if len(w.digitos) >= 10 else "O número precisa ter DDD + telefone.",
                dica="Digite só os números: o Vertex coloca o (DDD) e o hífen sozinho.",
            ),
        ]

    def etapa_documentos():
        campos["cpf"] = CpfCnpjField("000.000.000-00")
        campos["email"] = EmailField()
        return [
            CampoEtapa(
                "CPF ou CNPJ", campos["cpf"],
                valida=lambda w: None if len(_digitos(w.text())) in (11, 14) else "CPF tem 11 números e CNPJ tem 14.",
            ),
            CampoEtapa(
                "E-mail", campos["email"],
                valida=lambda w: None if email_valido(w.text()) else "Esse e-mail parece incompleto (ex.: nome@exemplo.com).",
            ),
        ]

    def etapa_credito():
        campos["limite"] = ValoresRapidos([100, 200, 500, 1000])
        return [CampoEtapa(
            "Limite de crédito (fiado)", campos["limite"],
            dica="Quanto ele pode dever ao mesmo tempo. Você muda quando quiser na ficha dele.",
        )]

    def resumo():
        return [
            ("Nome", campos["nome"].text()),
            ("WhatsApp", campos["whatsapp"].text()),
            ("CPF/CNPJ", campos["cpf"].text()),
            ("E-mail", campos["email"].text()),
            ("Limite de crédito", formatar_moeda(campos["limite"].value())),
        ]

    def concluir(assistente):
        interno.nome.setText(campos["nome"].text().strip())
        interno.whatsapp.setText(campos["whatsapp"].text())
        interno.cpf.setText(campos["cpf"].text())
        interno.email.setText(campos["email"].text().strip())
        if campos["limite"].value() > 0:
            interno.limite_credito.setText(_decimal_br(campos["limite"].value()))
        interno.salvar()
        assistente.aguardar_salvamento(interno.bt_salvar)

    passos = [
        dict(nome="Contato", titulo="Quem é o cliente?", campos=etapa_contato,
             dica="Só o nome é obrigatório. O WhatsApp pode ficar em branco."),
        dict(nome="Documentos", titulo="Quer guardar documento e e-mail?", campos=etapa_documentos,
             opcional=True, dica="Opcional. Se preencher, conferimos o formato."),
        dict(nome="Crédito", titulo="Qual o limite do fiado?", campos=etapa_credito,
             opcional=True, dica="Toque num valor ou digite. Ele vale para as compras fiado."),
        dict(nome="Revisão", titulo="Tudo certo?", revisao=True, resumo=resumo,
             dica="Confira antes de cadastrar."),
    ]
    assistente = AssistenteDialogo(
        "Novo cliente", "users", passos, "Cadastrar cliente", concluir, interno=interno, parent=parent,
    )
    interno.accepted.connect(assistente.accept)
    return assistente


# ----------------------------------------------------------------------
# PRODUTO
# ----------------------------------------------------------------------

_MODOS = (("Unidade", "UN"), ("Kg", "KG"), ("Litro", "L"))


def novo_produto_assistente(parent=None):
    from telas.cadastro_produto import CadastroProdutoWindow
    from telas.cadastro_produto.categorias_marcas import _criar_categoria_com_nome

    interno = CadastroProdutoWindow()
    campos = {}

    def etapa_identificacao():
        campos["codigo"] = CampoTexto("Bipe ou digite o código de barras")
        campos["nome"] = CampoTexto("Ex.: Mochila preta escolar")

        # o código vai pro cadastro original, que consulta o produto sozinho;
        # se o nome ainda está vazio, aproveita o que ele achou
        def procurar():
            interno.codigo_barras.setText(campos["codigo"].text().strip())
            QTimer.singleShot(1800, preencher_nome)

        def preencher_nome():
            if not campos["nome"].text().strip() and interno.nome.text().strip():
                campos["nome"].setText(interno.nome.text().strip())

        campos["codigo"].textChanged.connect(procurar)
        return [
            CampoEtapa(
                "Código de barras", campos["codigo"],
                dica="Sem etiqueta? Deixe em branco: o Vertex cria um código interno (ex.: 0042).",
            ),
            CampoEtapa("Nome do produto", campos["nome"], obrigatorio=True),
        ]

    def etapa_venda():
        def criar_categoria(nome):
            rodar_em_thread(
                assistente, _criar_categoria_com_nome, nome.upper(), ao_sucesso=categoria_criada,
            )

        def categoria_criada(resultado):
            resposta, nome = resultado
            if resposta.status_code in (200, 201):
                campos["categoria"].adicionar(nome)

        campos["categoria"] = Escolha(
            _itens(interno.categoria), rotulo_nova="Nova categoria", ao_criar=criar_categoria,
        )
        campos["preco"] = campo_dinheiro()
        return [
            CampoEtapa("Categoria", campos["categoria"], dica="Ajuda nos filtros e relatórios."),
            CampoEtapa("Preço de venda (R$)", campos["preco"], obrigatorio=True),
        ]

    def etapa_estoque():
        campos["modo"] = Opcoes([nome for nome, _ in _MODOS])
        campos["estoque"] = Contador()
        # Kg/Litro vendem em fração: o estoque ganha casas decimais
        campos["modo"].mudou = lambda i: setattr(campos["estoque"], "casas", 3 if i else 0)
        return [
            CampoEtapa("Estoque inicial", campos["estoque"], dica="Pode deixar em zero e dar entrada depois."),
            CampoEtapa("Vendido por", campos["modo"]),
        ]

    def resumo():
        codigo = campos["codigo"].text().strip()
        return [
            ("Código de barras", codigo or "gerado automaticamente"),
            ("Nome", campos["nome"].text()),
            ("Categoria", campos["categoria"].texto()),
            ("Preço de venda", formatar_moeda(campos["preco"].value())),
            ("Estoque inicial", f"{campos['estoque'].text()} {campos['modo'].texto().lower()}"),
        ]

    def concluir(assistente):
        interno.codigo_barras.setText(campos["codigo"].text().strip())
        interno.nome.setText(campos["nome"].text().strip())
        if campos["categoria"].texto():
            interno.categoria.setCurrentText(campos["categoria"].texto())
        interno.preco_venda.setValue(campos["preco"].value())
        interno.selecionar_modo(_MODOS[campos["modo"].atual][1])
        interno.estoque.setValue(campos["estoque"].value())
        interno.salvar()  # valida e aceita; quem chamou salva e lê `dados`
        assistente.liberar()

    passos = [
        dict(nome="Identificação", titulo="Qual é o produto?", campos=etapa_identificacao,
             dica="Comece pelo código de barras e depois o nome. Só o nome é obrigatório."),
        dict(nome="Venda", titulo="Onde fica e quanto custa?", campos=etapa_venda,
             dica="A categoria ajuda nos filtros. O preço de venda é obrigatório."),
        dict(nome="Estoque", titulo="Quantos você tem?", campos=etapa_estoque, opcional=True,
             dica="Escolha como o produto é vendido."),
        dict(nome="Revisão", titulo="Tudo certo?", revisao=True, resumo=resumo,
             dica="Custo, marca, fotos e promoção você completa depois, em Editar."),
    ]
    assistente = AssistenteDialogo(
        "Novo produto", "package", passos, "Cadastrar produto", concluir, interno=interno, parent=parent,
    )
    interno.accepted.connect(assistente.accept)
    return assistente


# ----------------------------------------------------------------------
# CONTA A PAGAR (boleto)
# ----------------------------------------------------------------------

_REPETICOES = ("Uma vez", "Parcelado", "Todo mês")


def nova_despesa_assistente(parent=None):
    from telas.cadastro_despesa import CadastroDespesaDialog

    interno = CadastroDespesaDialog(parent=parent)
    campos = {}

    def etapa_boleto():
        campos["codigo"] = CampoTexto("Bipe o código de barras ou cole a linha digitável")
        campos["descricao"] = CampoTexto("Fornecedor ou o que é a conta (ex.: luz, aluguel)")
        # o código vai pro cadastro original, que lê o boleto sozinho
        # (valor, vencimento, fornecedor): a etapa seguinte já usa isso
        campos["codigo"].textChanged.connect(lambda t: interno.numero_boleto.setText(t))
        campos["codigo"].textChanged.connect(
            lambda _t: QTimer.singleShot(2500, preencher_descricao)
        )

        def preencher_descricao():
            if not campos["descricao"].text().strip() and interno.descricao.text().strip():
                campos["descricao"].setText(interno.descricao.text().strip())

        return [
            CampoEtapa(
                "Código do boleto", campos["codigo"],
                dica="Bipou ou colou? O Vertex lê o valor, o vencimento e o beneficiário sozinho.",
            ),
            CampoEtapa("Descrição", campos["descricao"], obrigatorio=True),
        ]

    def etapa_valor():
        campos["valor"] = campo_dinheiro()
        campos["vencimento"] = DataRapida()
        # o que o boleto lido já preencheu no cadastro original
        try:
            lido = float(interno.valor.text().replace(".", "").replace(",", "."))
        except ValueError:
            lido = 0.0
        if lido > 0:
            campos["valor"].setValue(lido)
        if interno.vencimento.date() != QDate.currentDate():
            campos["vencimento"].campo.setDate(interno.vencimento.date())
        return [
            CampoEtapa("Valor (R$)", campos["valor"], obrigatorio=True),
            CampoEtapa("Vencimento", campos["vencimento"], obrigatorio=True),
        ]

    def etapa_pagamento():
        campos["repeticao"] = Opcoes(list(_REPETICOES))
        campos["parcelas"] = Contador(3, minimo=2)
        campos["categoria"] = Escolha(_itens(interno.categoria))
        return [
            CampoEtapa("Como você paga?", _agrupar(campos["repeticao"], "Quantas parcelas?", campos["parcelas"])),
            CampoEtapa("Categoria", campos["categoria"]),
        ]

    def resumo():
        repeticao = campos["repeticao"].texto()
        if campos["repeticao"].atual == 1:
            repeticao += f" em {int(campos['parcelas'].value())}x"
        return [
            ("Código do boleto", campos["codigo"].text()),
            ("Descrição", campos["descricao"].text()),
            ("Valor", formatar_moeda(campos["valor"].value())),
            ("Vencimento", campos["vencimento"].text()),
            ("Pagamento", repeticao),
            ("Categoria", campos["categoria"].texto()),
        ]

    def concluir(assistente):
        interno.descricao.setText(campos["descricao"].text().strip())
        interno.valor.setText(_decimal_br(campos["valor"].value()))
        interno.vencimento.setDate(campos["vencimento"].date())
        interno.repeticao.setCurrentIndex(campos["repeticao"].atual)
        if campos["repeticao"].atual == 1:
            interno.parcelas.setValue(int(campos["parcelas"].value()))
        if campos["categoria"].texto():
            interno.categoria.setCurrentText(campos["categoria"].texto())
        interno.salvar()
        assistente.aguardar_salvamento(interno.bt_salvar)

    passos = [
        dict(nome="Boleto", titulo="Qual é a conta?", campos=etapa_boleto,
             dica="Bipe ou cole o código do boleto, ou só diga o que é. A descrição é obrigatória."),
        dict(nome="Valor", titulo="Quanto e quando vence?", campos=etapa_valor,
             dica="Valor e vencimento são obrigatórios. Toque num atalho de data ou escolha no calendário."),
        dict(nome="Pagamento", titulo="Como você paga?", campos=etapa_pagamento, opcional=True,
             dica="Conta fixa do mês, parcelada ou única. A categoria ajuda nos relatórios."),
        dict(nome="Revisão", titulo="Tudo certo?", revisao=True, resumo=resumo,
             dica="Pix, centro de custo, descontos e anexo do boleto você completa depois, em Editar."),
    ]
    assistente = AssistenteDialogo(
        "Novo boleto", "wallet", passos, "Cadastrar boleto", concluir, interno=interno, parent=parent,
    )
    interno.accepted.connect(assistente.accept)
    return assistente


def _agrupar(opcoes, rotulo_extra, extra):
    """Opções + (quando aparece) um campo extra logo abaixo."""
    from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

    from design import tokens

    caixa = QWidget()
    caixa.setStyleSheet("background:transparent;")
    lay = QVBoxLayout(caixa)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    lay.addWidget(opcoes)
    linha = QWidget()
    ll = QHBoxLayout(linha)
    ll.setContentsMargins(0, 0, 0, 0)
    lbl = QLabel(rotulo_extra)
    lbl.setStyleSheet(
        f"background:transparent; color:{tokens.TEXTO_SECUNDARIO};"
        f"font-size:{tokens.TAMANHO_SM}px; font-weight:600;"
    )
    ll.addWidget(lbl)
    ll.addWidget(extra)
    lay.addWidget(linha)
    # a linha do campo extra só aparece com a 2ª opção ("Parcelado")
    opcoes.mudou = lambda i: linha.setVisible(i == 1)
    linha.setVisible(False)
    return caixa
