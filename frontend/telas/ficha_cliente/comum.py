from datetime import datetime

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import (
    QPainter, QPainterPath, QPixmap,
)
from PySide6.QtWidgets import (
    QPushButton,
)

from services import api
from services.produto_service import listar_produtos
from services.venda_service import listar_vendas
from services.movimento_fiado_service import (
    saldo_cliente,
    listar_movimentos_cliente,
)
from services.worker import em_paralelo
from design import tokens


def _buscar_dados_recibo_pagamento(cliente_id, valor, momento):
    """Roda na worker thread -- valor/momento so' viajam de ida e volta
    junto com o resultado (ver services/worker.py: callback precisa
    ser metodo vinculado, nao lambda/closure). As 3 chamadas de rede
    sao independentes, entao disparam em paralelo."""
    saldo_depois, usuario, config_loja = em_paralelo(
        (saldo_cliente, cliente_id), (api.me,), (api.configuracoes,)
    )
    responsavel = (usuario or {}).get("nome") or "—"
    return saldo_depois, responsavel, config_loja, valor, momento


def _buscar_dados_ficha_cliente(cliente_id):
    """Roda na worker thread -- as 4 chamadas que
    FichaClienteDialog.carregar() precisa, independentes entre si,
    disparadas em paralelo."""
    saldo, vendas, produtos, movimentos = em_paralelo(
        (saldo_cliente, cliente_id),
        (listar_vendas,),
        (listar_produtos,),
        (listar_movimentos_cliente, cliente_id),
    )
    vendas_por_id = {v["id"]: v for v in vendas}
    nomes_produto = {p["id"]: p["nome"] for p in produtos}
    return saldo, vendas_por_id, nomes_produto, movimentos


def _pixmap_circular(pixmap, tamanho):
    """Recorta um QPixmap qualquer num círculo — usado pra mostrar a foto
    do cliente no lugar das iniciais do Avatar, sem perder o formato
    redondo padrão do design system (setStyleSheet com border-radius não
    recorta o conteúdo de um pixmap, só o fundo do widget)."""

    escalado = pixmap.scaled(
        tamanho, tamanho, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
    )

    resultado = QPixmap(tamanho, tamanho)
    resultado.fill(Qt.transparent)

    pintor = QPainter(resultado)
    pintor.setRenderHint(QPainter.Antialiasing)

    caminho = QPainterPath()
    caminho.addEllipse(0, 0, tamanho, tamanho)
    pintor.setClipPath(caminho)

    x = (tamanho - escalado.width()) // 2
    y = (tamanho - escalado.height()) // 2
    pintor.drawPixmap(x, y, escalado)
    pintor.end()

    return resultado


FORMAS_PAGAMENTO = [
    ("Dinheiro", "DINHEIRO"),
    ("PIX", "PIX"),
    ("Cartão", "CARTAO"),
    ("Transferência", "TRANSFERENCIA"),
    ("Cheque", "CHEQUE"),
]


NOMES_FORMA_FIADO = {valor: rotulo for rotulo, valor in FORMAS_PAGAMENTO}


_ICONES_FORMA_PAGAMENTO = {
    "DINHEIRO": "dollar-sign",
    "PIX": "refresh-cw",
    "CARTAO": "credit-card",
    "TRANSFERENCIA": "arrow-up",
    "CHEQUE": "file-text",
}


def _dia_com_hora_atual(data_qt):
    """O dialogo so escolhe o dia (Hoje/Ontem); a hora vem do relogio,
    senao o lancamento fica "as 00:00" no recibo e nas listas do Inicio."""
    agora = datetime.now()
    return datetime(
        data_qt.year(), data_qt.month(), data_qt.day(),
        agora.hour, agora.minute, agora.second,
    ).isoformat()


def _parse_data(texto):
    try:
        return datetime.fromisoformat(texto)
    except (ValueError, TypeError):
        return None


def _botao_data_rapida(rotulo, campo_data, delta_dias):
    """Botão "Hoje"/"Ontem" que preenche um QDateEdit num clique só --
    evita abrir o calendário toda vez pra um lançamento que quase
    sempre é datado de hoje (ou, no máximo, ontem)."""

    bt = QPushButton(rotulo)
    bt.setCursor(Qt.PointingHandCursor)
    bt.setAutoDefault(False)
    bt.setFixedHeight(44)
    bt.setStyleSheet(f"""
        QPushButton {{
            background:{tokens.CARD}; border:1.5px solid {tokens.BORDA};
            border-radius:{tokens.RADIUS_SM}px; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700; padding:0 14px;
        }}
        QPushButton:hover {{ border-color:{tokens.PRIMARIA}; color:{tokens.PRIMARIA}; }}
    """)
    bt.clicked.connect(
        lambda: campo_data.setDate(QDate.currentDate().addDays(delta_dias))
    )
    return bt
