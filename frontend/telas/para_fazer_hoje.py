"""Bloco "Para fazer hoje" do Início (Vertex 2.0): no maximo 3 cartoes
com o que pede acao -- fiado atrasado, estoque pra repor, boletos
vencendo -- cada um com um botao que abre a tela ja' filtrada.
Calculado com os dados que o Resumo do dia ja' carrega (nada de
endpoint novo)."""
from collections import defaultdict
from datetime import date, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from design import tokens
from design.icons import icone
from services import cliente_analise
from utils.formatacao import formatar_moeda

PRAZO_COBRANCA_DIAS = 60  # igual ao limite de bom pagador (2 meses)
JANELA_BOLETOS_DIAS = 7


def _data(texto):
    try:
        return date.fromisoformat(str(texto)[:10])
    except (TypeError, ValueError):
        return None


def tarefas_do_dia(produtos, contas_pagar, clientes, movimentos_fiado,
                   hoje=None, financeiro=True):
    """[{id, titulo, detalhe, acao, variante}] -- so' o que precisa de acao."""
    hoje = hoje or date.today()
    tarefas = []

    movs = defaultdict(list)
    for m in movimentos_fiado:
        movs[m.get("cliente_id")].append(m)
    atrasados = []
    for c in clientes:
        if not c.get("ativo", True) or c.get("negativado"):
            continue
        agr = cliente_analise.calcular_agregados(c, movs.get(c.get("id"), []))
        if cliente_analise.eh_inadimplente(agr, PRAZO_COBRANCA_DIAS):
            atrasados.append(float(agr.get("saldo_devedor") or 0))
    if atrasados:
        n = len(atrasados)
        tarefas.append({
            "id": "fiado",
            "titulo": f"{n} cliente{'s' if n > 1 else ''} com fiado atrasado",
            "detalhe": f"{formatar_moeda(sum(atrasados))} sem pagamento há mais de {PRAZO_COBRANCA_DIAS} dias",
            "acao": "Ver quem cobrar",
            "variante": "erro",
        })

    ativos = [p for p in produtos if p.get("ativo", True)]
    repor = [p for p in ativos if p.get("estoque", 0) <= p.get("estoque_minimo", 0)]
    if repor:
        zerados = sum(1 for p in repor if p.get("estoque", 0) <= 0)
        n = len(repor)
        tarefas.append({
            "id": "estoque",
            "titulo": f"{n} produto{'s' if n > 1 else ''} para repor",
            "detalhe": f"{zerados} sem estoque" if zerados else "Estoque no mínimo ou abaixo",
            "acao": "Ver lista de compra",
            "variante": "alerta",
        })

    if financeiro:
        limite = hoje + timedelta(days=JANELA_BOLETOS_DIAS)
        vencendo = [
            b for b in contas_pagar
            if b.get("status") == "PENDENTE"
            and _data(b.get("data_vencimento")) is not None
            and _data(b.get("data_vencimento")) <= limite
        ]
        if vencendo:
            vencidos = sum(1 for b in vencendo if _data(b.get("data_vencimento")) < hoje)
            n = len(vencendo)
            total = formatar_moeda(sum(float(b.get("valor") or 0) for b in vencendo))
            titulo = (f"{vencidos} boleto{'s' if vencidos > 1 else ''} vencido{'s' if vencidos > 1 else ''}"
                      if vencidos else
                      f"{n} boleto{'s' if n > 1 else ''} vence{'m' if n > 1 else ''} em até {JANELA_BOLETOS_DIAS} dias")
            tarefas.append({
                "id": "boletos",
                "titulo": titulo,
                "detalhe": f"{total} ao todo" + (f" · mais {n - vencidos} a vencer" if vencidos and n > vencidos else ""),
                "acao": "Ver boletos",
                "variante": "erro" if vencidos else "info",
            })

    return tarefas


_CORES = {
    "erro": (tokens.ERRO_CLARO, tokens.ERRO, "alert-triangle"),
    "alerta": (tokens.ALERTA_CLARO, tokens.ALERTA_TEXTO, "package"),
    "info": (tokens.PRIMARIA_CLARA, tokens.PRIMARIA, "file-text"),
    "ok": (tokens.SUCESSO_CLARO, tokens.SUCESSO, "check"),
}


class _CartaoTarefa(QFrame):

    def __init__(self, tarefa, ao_clicar):
        super().__init__()
        self.setObjectName("cartaoTarefa")
        self.setStyleSheet(f"""
            QFrame#cartaoTarefa {{ background: {tokens.CARD}; border: 1px solid {tokens.BORDA};
                                   border-radius: {tokens.RADIUS_LG}px; }}
        """)
        fundo, cor, nome_icone = _CORES[tarefa["variante"]]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        topo = QHBoxLayout()
        topo.setSpacing(12)
        lbl_icone = QLabel()
        lbl_icone.setFixedSize(42, 42)
        lbl_icone.setAlignment(Qt.AlignCenter)
        lbl_icone.setPixmap(icone(nome_icone, cor=cor, tamanho=20).pixmap(20, 20))
        lbl_icone.setStyleSheet(f"background: {fundo}; border: none; border-radius: {tokens.RADIUS_MD}px;")
        topo.addWidget(lbl_icone, alignment=Qt.AlignTop)

        textos = QVBoxLayout()
        textos.setSpacing(3)
        titulo = QLabel(tarefa["titulo"])
        titulo.setWordWrap(True)
        titulo.setStyleSheet(f"background: transparent; border: none; color: {tokens.TEXTO}; "
                             f"font-size: {tokens.TAMANHO_LG}px; font-weight: 700;")
        detalhe = QLabel(tarefa["detalhe"])
        detalhe.setWordWrap(True)
        detalhe.setStyleSheet(f"background: transparent; border: none; color: {tokens.TEXTO_SECUNDARIO}; "
                              f"font-size: {tokens.TAMANHO_MD}px;")
        textos.addWidget(titulo)
        textos.addWidget(detalhe)
        topo.addLayout(textos, stretch=1)
        layout.addLayout(topo)

        if tarefa.get("acao"):
            self.botao = QPushButton(tarefa["acao"])
            self.botao.setCursor(Qt.PointingHandCursor)
            self.botao.setFixedHeight(40)
            principal = tarefa["variante"] == "erro"
            self.botao.setStyleSheet(f"""
                QPushButton {{ border-radius: {tokens.RADIUS_SM}px; font-size: {tokens.TAMANHO_MD}px; font-weight: 700;
                               background: {tokens.SECUNDARIA if principal else tokens.CARD};
                               color: {'white' if principal else tokens.TEXTO};
                               border: {'none' if principal else f'1px solid {tokens.BORDA_FORTE}'}; }}
                QPushButton:hover {{ background: {tokens.SECUNDARIA_HOVER if principal else tokens.FUNDO}; }}
            """)
            self.botao.clicked.connect(lambda: ao_clicar(tarefa["id"]))
            layout.addWidget(self.botao)


class ParaFazerHoje(QWidget):

    acao = Signal(str)  # id da tarefa: "fiado" | "estoque" | "boletos"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        externo.setSpacing(10)
        titulo = QLabel("Para fazer hoje")
        titulo.setStyleSheet(f"color: {tokens.TEXTO}; font-size: {tokens.TAMANHO_LG + 2}px; font-weight: 800;")
        externo.addWidget(titulo)
        self.linha = QHBoxLayout()
        self.linha.setSpacing(16)
        externo.addLayout(self.linha)
        self.cartoes = []

    def definir(self, tarefas):
        while self.linha.count():
            item = self.linha.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not tarefas:
            tarefas = [{"id": "ok", "titulo": "Tudo em dia por hoje",
                        "detalhe": "Nenhum fiado atrasado, estoque para repor ou boleto vencendo.",
                        "acao": None, "variante": "ok"}]
        self.cartoes = [_CartaoTarefa(t, self.acao.emit) for t in tarefas]
        for cartao in self.cartoes:
            self.linha.addWidget(cartao, stretch=1)
        # menos de 3 cartoes: nao esticar um so' na largura toda
        for _ in range(3 - len(self.cartoes)):
            self.linha.addStretch(1)
