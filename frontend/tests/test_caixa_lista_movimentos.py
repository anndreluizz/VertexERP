"""Lista de movimentos do caixa: venda no fiado nao parece dinheiro
entrando, e o estorno aparece ligado a' venda (caso real de 20/10)."""
from telas import caixa
from telas.caixa import _descricao_movimento, _tipo_exibido

MOVIMENTOS = [
    {"tipo": "VENDA", "forma_pagamento": "DINHEIRO", "valor": 36.0, "descricao": "Venda #151", "data": "2026-10-20T16:57:00"},
    {"tipo": "VENDA", "forma_pagamento": "PRAZO", "valor": 147.99, "descricao": "Venda #148", "data": "2026-10-20T15:50:00"},
    {"tipo": "ESTORNO", "forma_pagamento": "DINHEIRO", "valor": -150.0, "descricao": "Estorno da venda #146", "data": "2026-10-20T15:49:00"},
    {"tipo": "ESTORNO", "forma_pagamento": "PRAZO", "valor": -84.99, "descricao": "Estorno da venda #146", "data": "2026-10-20T15:49:00"},
]


def test_fiado_tem_tipo_proprio_e_aviso():
    assert _tipo_exibido(MOVIMENTOS[0]) == "VENDA"
    assert _tipo_exibido(MOVIMENTOS[1]) == "VENDA_FIADO"
    assert _descricao_movimento(MOVIMENTOS[1], "VENDA_FIADO") == "Venda #148 · não mexe no dinheiro do caixa"


def test_estorno_vira_venda_cancelada():
    assert _descricao_movimento(MOVIMENTOS[2], "ESTORNO") == "Venda #146 cancelada"
    assert _tipo_exibido(MOVIMENTOS[3]) == "ESTORNO_FIADO"


def test_fiado_recebido_em_dinheiro_entra_no_caixa():
    mov = {"tipo": "RECEBIMENTO_FIADO", "forma_pagamento": "DINHEIRO", "descricao": "Pagamento fiado - ANA"}
    assert _descricao_movimento(mov, _tipo_exibido(mov)) == "Pagamento fiado - ANA"


def test_lista_mostra_a_forma(_qapp):
    # so' a lista: a tela inteira busca dados no servidor ao abrir
    from types import SimpleNamespace
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

    dono = QWidget()
    tela = SimpleNamespace(lista_movimentos=QVBoxLayout(dono), lbl_sem_movimentos=QLabel())
    caixa.Caixa.carregar_movimentos(tela, MOVIMENTOS)
    textos = [tela.lista_movimentos.itemAt(i).widget().findChildren(QLabel)[2].text()
              for i in range(4)]
    assert textos[0] == "Venda #151 · Dinheiro"
    assert textos[1] == "Venda #148 · não mexe no dinheiro do caixa"

    # recarregar (botao Atualizar) troca as linhas, nao empilha
    caixa.Caixa.carregar_movimentos(tela, MOVIMENTOS[:1])
    assert tela.lista_movimentos.count() == 1


def test_numeros_e_diferenca_da_gaveta():
    resumo = {"saldo_inicial": 100, "vendas_dinheiro": 450, "vendas_pix": 340.5,
              "recebimentos_fiado_dinheiro": 62, "recebimentos_fiado_pix": 90,
              "sangrias": 200, "total_previsto": 412, "vendas_prazo": 154}
    movs = [{"tipo": "VENDA"}, {"tipo": "VENDA"}, {"tipo": "RECEBIMENTO_FIADO"},
            {"tipo": "SANGRIA"}, {"tipo": "VENDA", "forma_pagamento": "PRAZO"}]
    k = caixa.numeros_caixa(resumo, movs)
    assert k["entrou"] == 942.5 and k["saiu"] == 200 and k["gaveta"] == 412
    assert k["nota_entrou"] == "2 vendas + 1 pagamento de fiado"
    assert k["nota_saiu"] == "1 sangria"
    formas = caixa.formas_entrada(resumo)
    assert formas[-1][:3] == ("Fiado (fora da gaveta)", "PRAZO", 154)
    assert formas[0][3] == 54  # 512 de 942,50

    assert caixa.texto_diferenca(412, "410") == ("Faltou R$ 2,00", "erro")
    assert caixa.texto_diferenca(412, "1.412,00")[1] == "alerta"
    assert caixa.texto_diferenca(412, "412,00") == ("Bateu certinho", "sucesso")
    assert caixa.texto_diferenca(412, "") == ("—", "neutro")
