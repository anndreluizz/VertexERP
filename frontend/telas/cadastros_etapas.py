"""Cadastro de cliente, produto e conta a pagar em etapas.

Cada função devolve um AssistenteDialogo que se usa como o diálogo de
cadastro de sempre (`.exec()`, depois lê `cliente_salvo`/`dados`): por trás
dele há o diálogo de cadastro original, que é preenchido no fim e salva.
Editar continua abrindo o diálogo completo."""

from PySide6.QtCore import QDate, QTimer

from design.assistente import (
    AssistenteDialogo, CampoEtapa, Contador, DataRapida, Escolha, Opcoes,
    ValoresRapidos, campo_dinheiro, campo_percentual,
)
from design.widgets import CampoTexto
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
        campos["limite"].setValue(200)  # sugestão: troque ou toque noutro valor
        return [CampoEtapa(
            "Limite de crédito (fiado)", campos["limite"], obrigatorio=True,
            dica="Quanto ele pode dever ao mesmo tempo. Sem limite o fiado não trava nunca; "
                 "você muda quando quiser na ficha dele.",
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
        interno.limite_credito.setText(_decimal_br(campos["limite"].value()))
        interno.salvar()
        assistente.aguardar_salvamento(interno.bt_salvar)

    passos = [
        dict(nome="Contato", titulo="Quem é o cliente?", campos=etapa_contato,
             dica="Só o nome é obrigatório. O WhatsApp pode ficar em branco."),
        dict(nome="Documentos", titulo="Quer guardar documento e e-mail?", campos=etapa_documentos,
             opcional=True, dica="Opcional. Se preencher, conferimos o formato."),
        dict(nome="Crédito", titulo="Qual o limite do fiado?", campos=etapa_credito,
             dica="Toque num valor ou digite. Ele vale para as compras fiado."),
        dict(nome="Revisão", titulo="Tudo certo?", revisao=True, resumo=resumo,
             dica="Confira antes de cadastrar."),
    ]
    assistente = AssistenteDialogo(
        "Novo cliente", "users", passos, "Cadastrar cliente", concluir, interno=interno, parent=parent,
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


# ----------------------------------------------------------------------
# FORNECEDOR
# ----------------------------------------------------------------------

def novo_fornecedor_assistente(parent=None):
    from telas.cadastro_fornecedor import CadastroFornecedorDialog

    interno = CadastroFornecedorDialog(parent=parent)
    campos = {}

    def etapa_empresa():
        campos["razao"] = CampoTexto("Nome Ltda")
        campos["fantasia"] = CampoTexto("Como a loja chama o fornecedor")
        return [
            CampoEtapa("Razão social", campos["razao"], obrigatorio=True),
            CampoEtapa("Nome fantasia", campos["fantasia"]),
        ]

    def etapa_documento():
        campos["cnpj"] = CpfCnpjField("00.000.000/0000-00")
        campos["telefone"] = PhoneField("(00) 00000-0000")
        return [
            CampoEtapa(
                "CNPJ", campos["cnpj"], obrigatorio=True,
                valida=lambda w: None if len(_digitos(w.text())) == 14 and w.valido else "Informe um CNPJ válido (14 números).",
            ),
            CampoEtapa(
                "Telefone", campos["telefone"],
                valida=lambda w: None if len(w.digitos) >= 10 else "O número precisa ter DDD + telefone.",
            ),
        ]

    def etapa_contato():
        campos["email"] = EmailField("email@exemplo.com")
        campos["cidade"] = CampoTexto("Cidade")
        return [
            CampoEtapa(
                "E-mail", campos["email"],
                valida=lambda w: None if email_valido(w.text()) else "Esse e-mail parece incompleto (ex.: nome@exemplo.com).",
            ),
            CampoEtapa("Cidade", campos["cidade"]),
        ]

    def etapa_compras():
        campos["uf"] = CampoTexto("UF")
        campos["uf"].setMaxLength(2)
        campos["margem"] = campo_percentual()
        return [
            CampoEtapa("UF", campos["uf"]),
            CampoEtapa(
                "Margem padrão de venda", campos["margem"],
                dica="Sugerida no preço de venda dos produtos importados de NF-e.",
            ),
        ]

    def resumo():
        return [
            ("Razão social", campos["razao"].text()),
            ("Nome fantasia", campos["fantasia"].text()),
            ("CNPJ", campos["cnpj"].text()),
            ("Telefone", campos["telefone"].text()),
            ("E-mail", campos["email"].text()),
            ("Cidade / UF", " / ".join(p for p in (campos["cidade"].text(), campos["uf"].text()) if p)),
            ("Margem padrão", f"{campos['margem'].value():.2f} %".replace(".", ",")),
        ]

    def concluir(assistente):
        interno.razao_social.setText(campos["razao"].text().strip())
        interno.nome_fantasia.setText(campos["fantasia"].text().strip())
        interno.cnpj.setText(campos["cnpj"].text())
        interno.telefone.setText(campos["telefone"].text())
        interno.email.setText(campos["email"].text().strip())
        interno.cidade.setText(campos["cidade"].text().strip())
        interno.estado.setText(campos["uf"].text().strip())
        interno.margem_padrao.setValue(campos["margem"].value())
        interno.salvar()
        assistente.aguardar_salvamento(interno.bt_salvar)

    passos = [
        dict(nome="Empresa", titulo="Quem é o fornecedor?", campos=etapa_empresa,
             dica="Só a razão social é obrigatória."),
        dict(nome="Documento", titulo="CNPJ e telefone", campos=etapa_documento,
             dica="O CNPJ é obrigatório. O Vertex confere os números."),
        dict(nome="Contato", titulo="Como falar com ele?", campos=etapa_contato, opcional=True,
             dica="Opcional. Dá pra completar depois."),
        dict(nome="Compras", titulo="Estado e margem", campos=etapa_compras, opcional=True,
             dica="A margem ajuda no preço dos produtos que chegam por NF-e."),
        dict(nome="Revisão", titulo="Tudo certo?", revisao=True, resumo=resumo,
             dica="Confira antes de cadastrar."),
    ]
    assistente = AssistenteDialogo(
        "Novo fornecedor", "truck", passos, "Cadastrar fornecedor", concluir, interno=interno, parent=parent,
    )
    interno.accepted.connect(assistente.accept)
    return assistente


# ----------------------------------------------------------------------
# CATEGORIA DE PRODUTO
# ----------------------------------------------------------------------

def _criar_categoria(nome, descricao):
    from services.categoria_service import criar_categoria

    return criar_categoria(nome, descricao), nome


def nova_categoria_assistente(parent=None):
    """Cria a categoria e fica com o nome em `nome_criado`."""
    campos = {}

    def etapa_nome():
        campos["nome"] = CampoTexto("Ex.: Papelaria")
        campos["descricao"] = CampoTexto("Para que serve (opcional)")
        return [
            CampoEtapa("Nome da categoria", campos["nome"], obrigatorio=True),
            CampoEtapa("Descrição", campos["descricao"]),
        ]

    def resumo():
        return [("Nome", campos["nome"].text().strip().upper()), ("Descrição", campos["descricao"].text().strip())]

    def criada(resultado):
        from PySide6.QtWidgets import QMessageBox

        resposta, nome = resultado
        if resposta.status_code in (200, 201):
            assistente.nome_criado = nome
            assistente.accept()
            return
        try:
            erro = resposta.json()["detail"]
        except Exception:
            erro = resposta.text
        QMessageBox.critical(assistente, "Erro", str(erro))
        assistente.liberar()

    def concluir(a):
        a.executar(
            _criar_categoria, campos["nome"].text().strip().upper(),
            campos["descricao"].text().strip() or None, ao_sucesso=criada,
        )

    passos = [
        dict(nome="Categoria", titulo="Como se chama a categoria?", campos=etapa_nome,
             dica="O nome fica em maiúsculas, como as outras."),
        dict(nome="Revisão", titulo="Tudo certo?", revisao=True, resumo=resumo,
             dica="Confira antes de criar."),
    ]
    assistente = AssistenteDialogo(
        "Nova categoria", "package", passos, "Criar categoria", concluir, parent=parent,
    )
    assistente.nome_criado = None
    return assistente


# ----------------------------------------------------------------------
# USUÁRIO
# ----------------------------------------------------------------------

def novo_usuario_assistente(perfis=None, parent=None):
    from telas.gerenciar_usuarios import SENHA_MINIMA, NovoUsuarioDialog

    interno = NovoUsuarioDialog(perfis, parent=parent)
    campos = {}

    def etapa_dados():
        campos["nome"] = CampoTexto("Ex.: Maria da Silva")
        campos["email"] = EmailField("email@exemplo.com")
        return [
            CampoEtapa("Nome completo", campos["nome"], obrigatorio=True),
            CampoEtapa(
                "E-mail (é o login)", campos["email"], obrigatorio=True,
                valida=lambda w: None if "@" in w.text() and email_valido(w.text()) else "Esse e-mail parece incompleto (ex.: nome@exemplo.com).",
            ),
        ]

    def etapa_senha():
        # os campos de senha do cadastro original (com o olhinho de mostrar)
        campos["senha"], campos["confirmar"] = interno.senha, interno.confirmar
        return [
            CampoEtapa(
                "Senha", interno.senha, obrigatorio=True,
                valida=lambda w: None if len(w.text()) >= SENHA_MINIMA else f"A senha precisa ter pelo menos {SENHA_MINIMA} caracteres.",
                dica=f"Mínimo de {SENHA_MINIMA} caracteres.",
            ),
            CampoEtapa(
                "Confirmar senha", interno.confirmar, obrigatorio=True,
                valida=lambda w: None if w.text() == interno.senha.text() else "A confirmação não é igual à senha.",
            ),
        ]

    def etapa_perfil():
        campos["perfil"] = Escolha(
            [interno.perfil.itemText(i) for i in range(interno.perfil.count())], max_botoes=0,
        )
        return [CampoEtapa("Perfil de acesso", campos["perfil"], dica="Dá pra trocar depois.")]

    def resumo():
        return [
            ("Nome", campos["nome"].text()),
            ("E-mail (login)", campos["email"].text()),
            ("Senha", "•" * len(interno.senha.text())),
            ("Perfil", campos["perfil"].texto()),
        ]

    def concluir(assistente):
        interno.nome.setText(campos["nome"].text().strip())
        interno.email.setText(campos["email"].text().strip())
        interno.perfil.setCurrentIndex(max(interno.perfil.findText(campos["perfil"].texto()), 0))
        interno.criar()
        assistente.aguardar_salvamento(interno.bt_criar)

    passos = [
        dict(nome="Dados", titulo="Quem vai usar o sistema?", campos=etapa_dados,
             dica="O e-mail é o login do funcionário."),
        dict(nome="Senha", titulo="Crie uma senha de acesso", campos=etapa_senha,
             dica="Ele pode trocar depois, em Trocar senha."),
        dict(nome="Perfil", titulo="O que ele pode fazer?", campos=etapa_perfil,
             dica="O perfil define as telas e ações liberadas."),
        dict(nome="Revisão", titulo="Tudo certo?", revisao=True, resumo=resumo,
             dica="Confira antes de cadastrar."),
    ]
    assistente = AssistenteDialogo(
        "Novo usuário", "user", passos, "Cadastrar usuário", concluir, interno=interno, parent=parent,
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
