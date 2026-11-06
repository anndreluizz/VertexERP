"""Início do Vertex 2.0 (igual ao protótipo aprovado em 05/11/2026):
saudação, "Para fazer hoje", 4 números do dia, vendas por hora (hoje x
média do mesmo dia da semana) e os mais vendidos de hoje. Substitui o
antigo Dashboard, com os mesmos dados (nenhum endpoint novo)."""
from datetime import date, datetime, timedelta

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from design import tokens
from design.animations import contar
from design.fonts import familia_titulo, fonte
from design.privacidade import privacidade
from services.api import dashboard, me, usuario_tem_permissao
from services.caixa_service import caixa_aberto
from services.cliente_service import listar_clientes
from services.conta_pagar_service import listar_contas_pagar
from services.movimento_fiado_service import listar_movimentos
from services.produto_service import listar_produtos
from services.venda_service import listar_vendas
from services.worker import em_paralelo, rodar_em_thread
from services import preferencias_service
from telas.para_fazer_hoje import ParaFazerHoje, tarefas_do_dia
from utils.formatacao import formatar_moeda
from utils.periodo import inicio_historico

DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
DIAS_TITULO = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
HORAS = list(range(8, 20))  # 8h..19h -- horario da loja
SEMANAS_MEDIA = 4


def _quando(texto):
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "")[:19])
    except (TypeError, ValueError):
        return None


def _com_fallback(func, *args):
    try:
        return func(*args)
    except Exception:
        return []


def _buscar_dados_inicio():
    """Worker thread: as mesmas chamadas do antigo Dashboard + caixa."""
    loja_id = preferencias_service.carregar_loja_id()
    return em_paralelo(
        (me,),
        (dashboard,),
        (listar_vendas, loja_id, None, inicio_historico()),
        (listar_produtos,),
        (_com_fallback, listar_contas_pagar, loja_id),
        (_com_fallback, listar_clientes),
        (_com_fallback, listar_movimentos),
        (_com_fallback, caixa_aberto),
    )


def saudacao(agora):
    if agora.hour < 12:
        return "Bom dia"
    return "Boa tarde" if agora.hour < 18 else "Boa noite"


def resumo_inicio(vendas, dados, movimentos_fiado, produtos_por_id, hoje=None):
    """Tudo que a tela mostra, calculado de uma vez (testavel sem Qt)."""
    hoje = hoje or date.today()
    finalizadas = [v for v in vendas if v.get("status") == "FINALIZADA"]

    por_dia, qtd_dia = {}, {}
    for v in finalizadas:
        quando = _quando(v.get("data"))
        if quando:
            por_dia[quando.date()] = por_dia.get(quando.date(), 0.0) + float(v.get("valor_total") or 0)
            qtd_dia[quando.date()] = qtd_dia.get(quando.date(), 0) + 1

    vendas_hoje = float(dados.get("vendas_hoje", por_dia.get(hoje, 0)) or 0)
    qtd_hoje = int(dados.get("vendas_hoje_qtd", qtd_dia.get(hoje, 0)) or 0)

    semana_passada = hoje - timedelta(days=7)
    anterior = por_dia.get(semana_passada, 0.0)
    nota_vendas = f"{qtd_hoje} {'venda' if qtd_hoje == 1 else 'vendas'}"
    cor_vendas = tokens.TEXTO_SECUNDARIO
    if anterior > 0.009:
        variacao = (vendas_hoje - anterior) / anterior * 100
        nota_vendas += f" · {variacao:+.0f}% que {DIAS[semana_passada.weekday()]} passada"
        cor_vendas = tokens.SUCESSO if variacao >= 0 else tokens.ERRO

    mes = [d for d in por_dia if d.year == hoje.year and d.month == hoje.month]
    total_mes = sum(por_dia[d] for d in mes)
    qtd_mes = sum(qtd_dia[d] for d in mes)
    ticket = vendas_hoje / qtd_hoje if qtd_hoje else 0.0
    ticket_mes = total_mes / qtd_mes if qtd_mes else 0.0

    pagamentos_hoje = [
        m for m in movimentos_fiado
        if m.get("tipo") == "PAGAMENTO" and (_quando(m.get("data")) or datetime.min).date() == hoje
    ]
    recebido = sum(float(m.get("valor") or 0) for m in pagamentos_hoje)

    # vendas por hora: hoje x media das ultimas 4 do mesmo dia da semana
    hora_hoje = {h: 0.0 for h in HORAS}
    hora_media = {h: 0.0 for h in HORAS}
    dias_media = {hoje - timedelta(days=7 * k) for k in range(1, SEMANAS_MEDIA + 1)}
    top = {}
    for v in finalizadas:
        quando = _quando(v.get("data"))
        if not quando or quando.hour not in hora_hoje:
            continue
        valor = float(v.get("valor_total") or 0)
        if quando.date() == hoje:
            hora_hoje[quando.hour] += valor
            for item in v.get("itens", []):
                pid = item.get("produto_id")
                top[pid] = top.get(pid, 0) + float(item.get("quantidade") or 0)
        elif quando.date() in dias_media:
            hora_media[quando.hour] += valor / SEMANAS_MEDIA

    mais_vendidos = [
        ((produtos_por_id.get(pid) or {}).get("nome") or f"Produto #{pid}", qtd)
        for pid, qtd in sorted(top.items(), key=lambda kv: -kv[1])[:5]
    ]

    return {
        "vendas_hoje": vendas_hoje, "nota_vendas": nota_vendas, "cor_vendas": cor_vendas,
        "ticket": ticket, "ticket_mes": ticket_mes,
        "caixa": float(dados.get("saldo_caixa", 0) or 0),
        "recebido_fiado": recebido, "pagamentos_fiado": len(pagamentos_hoje),
        "horas": [(h, hora_hoje[h], hora_media[h]) for h in HORAS],
        "mais_vendidos": mais_vendidos,
        "dia_semana": DIAS[hoje.weekday()],
    }


def _cartao(nome):
    frame = QFrame()
    frame.setObjectName(nome)
    frame.setStyleSheet(f"""
        QFrame#{nome} {{ background:{tokens.CARD}; border:1px solid {tokens.BORDA};
                         border-radius:{tokens.RADIUS_LG}px; }}
    """)
    return frame


def _rotulo(texto, tamanho, cor, peso=400, titulo=False):
    lbl = QLabel(texto)
    familia = f"font-family:'{familia_titulo()}';" if titulo else ""
    lbl.setStyleSheet(f"background:transparent; border:none; color:{cor}; "
                      f"font-size:{tamanho}px; font-weight:{peso}; {familia}")
    return lbl


class _Numero(QFrame):
    """Cartao de numero do dia: rotulo, valor grande (conta ate' o valor)
    e uma nota colorida embaixo."""

    def __init__(self, rotulo):
        super().__init__()
        self.setObjectName("numeroInicio")
        self.setStyleSheet(f"""
            QFrame#numeroInicio {{ background:{tokens.CARD}; border:1px solid {tokens.BORDA};
                                   border-radius:{tokens.RADIUS_LG}px; }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(6)
        layout.addWidget(_rotulo(rotulo, tokens.TAMANHO_MD, tokens.TEXTO_SECUNDARIO, 600))
        self.lbl_valor = _rotulo("—", 28, tokens.TEXTO, 700, titulo=True)
        layout.addWidget(self.lbl_valor)
        self.lbl_nota = _rotulo("", tokens.TAMANHO_MD, tokens.TEXTO_SECUNDARIO)
        self.lbl_nota.setWordWrap(True)
        layout.addWidget(self.lbl_nota)

    def definir(self, valor, nota, cor_nota=None):
        contar(self.lbl_valor, valor)
        privacidade.definir_texto(self.lbl_nota, nota)
        self.lbl_nota.setStyleSheet(
            f"background:transparent; border:none; color:{cor_nota or tokens.TEXTO_SECUNDARIO}; "
            f"font-size:{tokens.TAMANHO_MD}px;"
        )


class BarrasHora(QWidget):
    """Vendas por hora: barra cinza (media) e azul (hoje) por hora."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(200)
        self._dados = []
        self.setAccessibleName("Gráfico de vendas por hora: hoje e média")

    def definir(self, horas):
        self._dados = horas
        self.update()

    def paintEvent(self, _evento):
        if not self._dados:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        altura_rotulo = 22
        area = self.height() - altura_rotulo - 4
        maior = max([max(h, m) for _, h, m in self._dados] + [0.01])
        largura_grupo = self.width() / len(self._dados)
        barra = min(18.0, largura_grupo * 0.32)
        fonte_rotulo = QFont(fonte(tokens.TAMANHO_SM))
        p.setFont(fonte_rotulo)
        p.setPen(QColor(tokens.BORDA))
        p.drawLine(0, area, self.width(), area)
        for i, (hora, hoje, media) in enumerate(self._dados):
            centro = largura_grupo * i + largura_grupo / 2
            for deslocamento, valor, cor in ((-barra - 1.5, media, tokens.BORDA_FORTE),
                                             (1.5, hoje, tokens.PRIMARIA)):
                h = (area - 6) * valor / maior
                if h > 0:
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(cor))
                    p.drawRoundedRect(QRectF(centro + deslocamento, area - h, barra, h), 4, 4)
            p.setPen(QColor(tokens.TEXTO_TERCIARIO))
            p.drawText(QRectF(centro - largura_grupo / 2, area + 4, largura_grupo, altura_rotulo),
                       Qt.AlignCenter, f"{hora}h")
        p.end()


class Inicio(QWidget):

    tarefa_escolhida = Signal(str)  # "fiado" | "estoque" | "boletos"

    def __init__(self, usuario_id=None):
        super().__init__()
        self._carregando = False
        self._financeiro = usuario_tem_permissao("financeiro.ver")
        self.setStyleSheet(f"background:{tokens.FUNDO};")

        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.NoFrame)
        rolagem.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        externo.addWidget(rolagem)

        conteudo = QWidget()
        conteudo.setStyleSheet("background:transparent;")
        rolagem.setWidget(conteudo)
        miolo = QHBoxLayout(conteudo)
        miolo.setContentsMargins(24, 26, 24, 40)
        coluna = QWidget()
        coluna.setMaximumWidth(1320)
        miolo.addWidget(coluna)
        layout = QVBoxLayout(coluna)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(22)

        # ---- saudacao + selos
        topo = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(4)
        self.lbl_saudacao = _rotulo("", 32, tokens.TEXTO, 700, titulo=True)
        self.lbl_data = _rotulo("", 15, tokens.TEXTO_SECUNDARIO)
        col.addWidget(self.lbl_saudacao)
        col.addWidget(self.lbl_data)
        topo.addLayout(col, stretch=1)
        self.selo_caixa = QLabel()
        topo.addWidget(self.selo_caixa, alignment=Qt.AlignBottom)
        layout.addLayout(topo)

        # ---- para fazer hoje
        self.para_fazer = ParaFazerHoje()
        self.para_fazer.acao.connect(self.tarefa_escolhida)
        layout.addWidget(self.para_fazer)

        # ---- numeros do dia
        grade = QGridLayout()
        grade.setSpacing(14)
        self.num_vendas = _Numero("Vendas hoje" if self._financeiro else "Minhas vendas hoje")
        self.num_caixa = _Numero("No caixa agora")
        self.num_ticket = _Numero("Ticket médio")
        self.num_fiado = _Numero("Recebido de fiado")
        numeros = [self.num_vendas, self.num_caixa, self.num_ticket, self.num_fiado]
        if not self._financeiro:
            # vendedor nao ve dinheiro da loja (mesma regra do antigo painel)
            numeros = [self.num_vendas, self.num_fiado]
        for i, numero in enumerate(numeros):
            grade.addWidget(numero, 0, i)
            grade.setColumnStretch(i, 1)
        layout.addLayout(grade)

        # ---- vendas por hora + mais vendidos
        linha = QHBoxLayout()
        linha.setSpacing(14)
        cartao_grafico = _cartao("cartaoHoras")
        lg = QVBoxLayout(cartao_grafico)
        lg.setContentsMargins(20, 18, 20, 18)
        lg.setSpacing(4)
        lg.addWidget(_rotulo("Vendas por hora", 17, tokens.TEXTO, 700))
        self.lbl_legenda_horas = _rotulo("", tokens.TAMANHO_MD, tokens.TEXTO_SECUNDARIO)
        lg.addWidget(self.lbl_legenda_horas)
        self.barras = BarrasHora()
        lg.addWidget(self.barras, stretch=1)
        cartao_grafico.setVisible(self._financeiro)
        linha.addWidget(cartao_grafico, stretch=3)

        cartao_top = _cartao("cartaoTop")
        self.lista_top = QVBoxLayout(cartao_top)
        self.lista_top.setContentsMargins(20, 18, 20, 18)
        self.lista_top.setSpacing(0)
        linha.addWidget(cartao_top, stretch=2)
        layout.addLayout(linha)
        layout.addStretch()

        self.carregar()

    def carregar(self):
        if self._carregando:
            return
        self._carregando = True
        rodar_em_thread(self, _buscar_dados_inicio, ao_sucesso=self._ao_carregar,
                        ao_erro=self._ao_erro, ao_finalizar=self._ao_finalizar)

    def _ao_finalizar(self):
        self._carregando = False

    def _ao_erro(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível carregar o Início.\n{erro}")

    def _ao_carregar(self, resultado):
        try:
            (usuario, dados, vendas, produtos, contas, clientes, movimentos, caixa) = resultado
            agora = datetime.now()
            nome = (usuario.get("nome") or "").split(" ")[0] or "tudo bem"
            self.lbl_saudacao.setText(f"{saudacao(agora)}, {nome}")
            self.lbl_data.setText(
                f"{DIAS_TITULO[agora.weekday()]}, {agora.day} de {MESES[agora.month - 1]}"
            )
            self._pintar_selo_caixa(caixa if isinstance(caixa, dict) else None)

            self.para_fazer.definir(tarefas_do_dia(
                produtos, contas, clientes, movimentos, financeiro=self._financeiro,
            ))

            r = resumo_inicio(vendas, dados or {}, movimentos, {p["id"]: p for p in produtos})
            self.num_vendas.definir(formatar_moeda(r["vendas_hoje"]), r["nota_vendas"], r["cor_vendas"])
            self.num_caixa.definir(formatar_moeda(r["caixa"]), "nos caixas abertos agora")
            self.num_ticket.definir(formatar_moeda(r["ticket"]), f"Média do mês: {formatar_moeda(r['ticket_mes'])}")
            n = r["pagamentos_fiado"]
            self.num_fiado.definir(
                formatar_moeda(r["recebido_fiado"]),
                f"{n} {'pagamento' if n == 1 else 'pagamentos'} hoje",
                tokens.SUCESSO if n else None,
            )
            self.lbl_legenda_horas.setText(
                f"Hoje (azul) e média das últimas {SEMANAS_MEDIA} {r['dia_semana']}s (cinza)"
            )
            self.barras.definir(r["horas"])
            self._pintar_top(r["mais_vendidos"])
        except Exception as erro:
            self._ao_erro(erro)

    def _pintar_selo_caixa(self, caixa):
        if caixa:
            quando = _quando(caixa.get("data_abertura"))
            texto = f"Caixa aberto desde {quando:%H:%M}" if quando else "Caixa aberto"
            fundo, cor = tokens.SUCESSO_CLARO, tokens.SUCESSO
        else:
            texto, fundo, cor = "Caixa fechado", tokens.ALERTA_CLARO, tokens.ALERTA_TEXTO
        self.selo_caixa.setText(texto)
        self.selo_caixa.setStyleSheet(
            f"background:{fundo}; color:{cor}; border-radius:14px; padding:6px 14px; "
            f"font-size:{tokens.TAMANHO_MD}px; font-weight:600;"
        )

    def _pintar_top(self, mais_vendidos):
        while self.lista_top.count():
            item = self.lista_top.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        titulo = _rotulo("Mais vendidos hoje", 17, tokens.TEXTO, 700)
        titulo.setContentsMargins(0, 0, 0, 8)
        self.lista_top.addWidget(titulo)
        if not mais_vendidos:
            self.lista_top.addWidget(_rotulo("Nenhuma venda hoje ainda.", tokens.TAMANHO_MD,
                                             tokens.TEXTO_TERCIARIO))
        for pos, (nome, qtd) in enumerate(mais_vendidos, start=1):
            linha = QFrame()
            linha.setObjectName("linhaTop")
            linha.setStyleSheet(f"QFrame#linhaTop {{ border:none; border-top:1px solid {tokens.BORDA}; }}")
            hl = QHBoxLayout(linha)
            hl.setContentsMargins(0, 9, 0, 9)
            hl.setSpacing(10)
            hl.addWidget(_rotulo(str(pos), tokens.TAMANHO_MD, tokens.TEXTO_TERCIARIO, 700))
            lbl_nome = _rotulo(nome, tokens.TAMANHO_MD, tokens.TEXTO, 600)
            hl.addWidget(lbl_nome, stretch=1)
            hl.addWidget(_rotulo(f"{qtd:g} un", tokens.TAMANHO_SM, tokens.TEXTO_SECUNDARIO))
            self.lista_top.addWidget(linha)
        self.lista_top.addStretch()
