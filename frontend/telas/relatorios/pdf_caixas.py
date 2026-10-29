"""Relatório de caixas em PDF (aba Caixa de Relatórios): resumo do
período, produtos vendidos e, caixa por caixa, cada venda com os itens,
os recebimentos de fiado, suprimentos e sangrias e a conferência."""

from datetime import datetime, timedelta
from html import escape

from services import api
from services.caixa_service import (
    entradas_caixa, historico_caixa, listar_movimentos_caixa, resumo_caixa_por_id,
)
from services.venda_service import listar_vendas_periodo
from utils.formatacao import formatar_moeda, linhas_resumo_caixa, nome_forma

_ROTULOS = {
    "RECEBIMENTO_FIADO": "Fiado recebido",
    "SUPRIMENTO": "Suprimento",
    "SANGRIA": "Sangria",
    "ESTORNO": "Estorno",
    "PAGAMENTO": "Conta paga",
}


def _dt(texto):
    return datetime.fromisoformat(str(texto)[:19]) if texto else None


def _fmt(texto, formato="%d/%m/%Y %H:%M"):
    d = _dt(texto)
    return d.strftime(formato) if d else "—"


def _moeda(valor):
    valor = float(valor or 0)
    return ("- " if valor <= -0.005 else "") + formatar_moeda(abs(valor))


def buscar_dados(inicio, fim, loja_id):
    """Worker thread. inicio None = tudo."""
    caixas = historico_caixa(loja_id, 500)
    caixas = [
        c for c in caixas
        if (inicio is None or _dt(c["data_abertura"]).date() >= inicio)
        and _dt(c["data_abertura"]).date() <= fim
    ]
    caixas.sort(key=lambda c: c["data_abertura"])
    detalhes = [
        (c, resumo_caixa_por_id(c["id"]) or {}, listar_movimentos_caixa(c["id"]) or [])
        for c in caixas
    ]
    vendas = []
    if caixas:
        primeiro = _dt(caixas[0]["data_abertura"]).date()
        # caixa aberto num dia pode vender depois da meia-noite
        vendas = listar_vendas_periodo(primeiro, fim + timedelta(days=1), loja_id)
    return {
        "inicio": inicio, "fim": fim, "detalhes": detalhes, "vendas": vendas,
        "entradas": entradas_caixa(inicio, fim, loja_id), "config": api.configuracoes() or {},
    }


def vendas_do_caixa(caixa, vendas):
    """Vendas do operador entre a abertura e o fechamento do caixa (a
    venda não guarda o caixa; um caixa é de um usuário só)."""
    abriu = _dt(caixa["data_abertura"])
    fechou = _dt(caixa.get("data_fechamento")) or datetime.max
    return sorted(
        (v for v in vendas
         if v.get("usuario_id") == caixa.get("usuario_id") and abriu <= _dt(v["data"]) <= fechou),
        key=lambda v: v["data"],
    )


def _pagamento(venda):
    forma = nome_forma(venda.get("forma_pagamento")) or ""
    if venda.get("forma_pagamento_2"):
        forma += f" + {nome_forma(venda['forma_pagamento_2'])} {formatar_moeda(venda.get('valor_forma_2'))}"
    return forma


def _tabela(cabecalho, linhas, vazio):
    th = "".join(f"<th align='left'>{c}</th>" for c in cabecalho)
    if not linhas:
        linhas = [[f"<i>{vazio}</i>"] + [""] * (len(cabecalho) - 1)]
    corpo = "".join(
        "<tr>" + "".join(
            f"<td{' align=right' if j == len(l) - 1 else ''}>{x}</td>" for j, x in enumerate(l)
        ) + "</tr>"
        for l in linhas
    )
    return (f"<table width='100%' border='1' cellspacing='0' cellpadding='4'>"
            f"<tr style='background:#e3ece5;'>{th}</tr>{corpo}</table>")


def _bloco_caixa(caixa, resumo, movimentos, vendas):
    validas = [v for v in vendas if v.get("status") != "CANCELADA"]
    linhas_vendas = []
    for v in vendas:
        cancelada = v.get("status") == "CANCELADA"
        itens = "<br>".join(
            f"{i['quantidade']}x {escape(i.get('produto_nome') or '')} "
            f"({formatar_moeda(i['valor_unitario'])})"
            for i in v.get("itens") or []
        )
        if float(v.get("desconto") or 0) >= 0.01:
            itens += f"<br><i>desconto {formatar_moeda(v['desconto'])}</i>"
        valor = formatar_moeda(v["valor_total"])
        linhas_vendas.append([
            _fmt(v["data"], "%H:%M"), f"#{v['id']}", escape(v.get("cliente_nome") or "—"), itens,
            "CANCELADA" if cancelada else _pagamento(v),
            f"<s>{valor}</s>" if cancelada else valor,
        ])
    outros = sorted(
        (m for m in movimentos if m.get("tipo") != "VENDA"), key=lambda m: m.get("data") or "",
    )
    linhas_outros = [
        [_fmt(m.get("data"), "%H:%M"), _ROTULOS.get(m.get("tipo"), m.get("tipo") or ""),
         escape(m.get("descricao") or ""), nome_forma(m.get("forma_pagamento")) or "",
         ("- " if m.get("tipo") in ("SANGRIA", "ESTORNO", "PAGAMENTO") else "") + formatar_moeda(m.get("valor"))]
        for m in outros
    ]

    previsto = float(resumo.get("total_previsto") or 0)
    contado = caixa.get("valor_contado")
    if contado is None:
        conferencia = "não contado" if caixa.get("status") == "FECHADO" else "caixa em aberto"
    else:
        dif = float(contado) - previsto
        conferencia = (f"contado {formatar_moeda(contado)} · "
                       + ("confere" if abs(dif) < 0.01 else
                          f"{'sobra' if dif > 0 else 'falta'} {formatar_moeda(abs(dif))}"))
    resumo_html = "".join(
        f"<tr><td>{r}</td><td align=right>{_moeda(x)}</td></tr>"
        for r, x in linhas_resumo_caixa(resumo)
    )
    obs = (caixa.get("observacoes") or "").strip()
    return f"""
    <h2 style="color:#1f3b2d; margin-top:18px;">Caixa de {_fmt(caixa['data_abertura'], '%d/%m/%Y')}
      · {escape(caixa.get('usuario_nome') or '—')}</h2>
    <p>Aberto {_fmt(caixa['data_abertura'])} · fechado {_fmt(caixa.get('data_fechamento'))}</p>
    <table cellspacing="0" cellpadding="2">{resumo_html}
      <tr><td>Vendas a prazo (fiado lançado)</td><td align=right>{formatar_moeda(resumo.get('vendas_prazo'))}</td></tr>
      <tr><td><b>Previsto na gaveta</b></td><td align=right><b>{formatar_moeda(previsto)}</b></td></tr>
      <tr><td>Conferência</td><td align=right>{conferencia}</td></tr>
      <tr><td><b>Total geral do turno</b></td><td align=right><b>{formatar_moeda(resumo.get('total_geral'))}</b></td></tr>
    </table>
    <h3>Vendas ({len(validas)}) · {formatar_moeda(sum(float(v['valor_total']) for v in validas))}</h3>
    {_tabela(["Hora", "Venda", "Cliente", "Itens", "Pagamento", "Valor"], linhas_vendas, "Nenhuma venda")}
    <h3>Recebimentos, suprimentos e sangrias</h3>
    {_tabela(["Hora", "Tipo", "Descrição", "Pagamento", "Valor"], linhas_outros, "Nada registrado")}
    {f"<p><b>Observações:</b> {escape(obs)}</p>" if obs else ""}
    """


def montar_html(dados, nome_loja, rotulo_periodo):
    detalhes, todas = dados["detalhes"], dados["vendas"]
    blocos, vendidas = [], []
    for caixa, resumo, movimentos in detalhes:
        vendas = vendas_do_caixa(caixa, todas)
        vendidas += [v for v in vendas if v.get("status") != "CANCELADA"]
        blocos.append(_bloco_caixa(caixa, resumo, movimentos, vendas))

    produtos = {}
    for v in vendidas:
        for i in v.get("itens") or []:
            p = produtos.setdefault(i.get("produto_nome") or f"#{i['produto_id']}", [0, 0.0])
            p[0] += i["quantidade"]
            p[1] += float(i["subtotal"])
    linhas_produtos = [
        [escape(nome), str(q), formatar_moeda(t)]
        for nome, (q, t) in sorted(produtos.items(), key=lambda kv: -kv[1][1])
    ]

    e = dados["entradas"] or {}

    def v(chave):
        return float(e.get(chave) or 0)

    resumo = [
        ("Total que entrou", v("total")), ("Dinheiro", v("dinheiro")), ("PIX", v("pix")),
        ("Cartão", v("cartao")), ("Fiado recebido (já somado acima)", v("fiado_recebido")),
        ("Vendido a prazo (ainda não entrou)", v("vendas_prazo")),
        ("Contas pagas", -v("contas_pagas")), ("Sangrias", -v("sangrias")),
        ("Resultado do período", v("sobrou")),
    ]
    resumo_html = "".join(
        f"<tr><td>{r}</td><td align=right>{_moeda(x)}</td></tr>" for r, x in resumo
    )
    gerado = datetime.now().strftime("%d/%m/%Y %H:%M")
    return f"""
    <div style="font-family:Arial; font-size:9pt;">
    <h1 style="color:#1f3b2d; margin-bottom:0;">{escape(nome_loja)}</h1>
    <p style="color:#666;">Relatório de caixas · {escape(rotulo_periodo)} · gerado em {gerado}</p>
    <h2 style="color:#1f3b2d;">Resumo do período</h2>
    <p>{len(detalhes)} caixas · {len(vendidas)} vendas</p>
    <table cellspacing="0" cellpadding="2">{resumo_html}</table>
    <h2 style="color:#1f3b2d;">Produtos vendidos</h2>
    {_tabela(["Produto", "Qtd", "Total"], linhas_produtos, "Nenhum produto vendido")}
    {"".join(blocos)}
    </div>
    """
