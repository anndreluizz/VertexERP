/// Um ponto da serie mensal (6 meses) usada nos graficos do dashboard
/// financeiro -- espelha backend/app/schemas/dashboard.py::SerieMensalItem.
class SerieMensalPonto {
  const SerieMensalPonto({required this.mes, required this.valor});

  factory SerieMensalPonto.fromJson(Map<String, dynamic> json) {
    return SerieMensalPonto(
      mes: json['mes'] as String,
      valor: (json['valor'] as num).toDouble(),
    );
  }

  final String mes;
  final double valor;

  /// 'ago' a partir de '2026-08' -- rotulo curto pro eixo do grafico.
  String get rotuloCurto {
    const nomes = [
      'jan', 'fev', 'mar', 'abr', 'mai', 'jun',
      'jul', 'ago', 'set', 'out', 'nov', 'dez',
    ];
    final partes = mes.split('-');
    final indice = int.parse(partes[1]) - 1;
    return nomes[indice];
  }

  Map<String, dynamic> toJson() => {'mes': mes, 'valor': valor};
}

/// Espelha backend/app/schemas/dashboard.py::DashboardResponse —
/// mesmo endpoint (GET /dashboard) que o Desktop ja usa.
class DashboardResumo {
  const DashboardResumo({
    required this.vendasHoje,
    required this.vendasHojeQtd,
    required this.vendasMes,
    required this.comprasHoje,
    required this.saldoCaixa,
    required this.contasReceber,
    required this.contasPagar,
    required this.clientes,
    required this.fornecedores,
    required this.produtos,
    required this.estoqueBaixo,
    required this.contasVencidasQtd,
    required this.contasVencidasValor,
    required this.contasVencendoHojeQtd,
    required this.contasVencendoHojeValor,
    required this.contasPagasHojeQtd,
    required this.contasPagasHojeValor,
    required this.fiadoRecebidoHoje,
    required this.contasMesPago,
    required this.contasMesPendente,
    required this.serieRecebimentosMensal,
    required this.seriePagamentosMensal,
  });

  factory DashboardResumo.fromJson(Map<String, dynamic> json) {
    return DashboardResumo(
      vendasHoje: (json['vendas_hoje'] as num).toDouble(),
      vendasHojeQtd: json['vendas_hoje_qtd'] as int,
      vendasMes: (json['vendas_mes'] as num).toDouble(),
      comprasHoje: (json['compras_hoje'] as num).toDouble(),
      saldoCaixa: (json['saldo_caixa'] as num).toDouble(),
      contasReceber: (json['contas_receber'] as num).toDouble(),
      contasPagar: (json['contas_pagar'] as num).toDouble(),
      clientes: json['clientes'] as int,
      fornecedores: json['fornecedores'] as int,
      produtos: json['produtos'] as int,
      estoqueBaixo: json['estoque_baixo'] as int,
      contasVencidasQtd: json['contas_vencidas_qtd'] as int? ?? 0,
      contasVencidasValor:
          (json['contas_vencidas_valor'] as num?)?.toDouble() ?? 0,
      contasVencendoHojeQtd: json['contas_vencendo_hoje_qtd'] as int? ?? 0,
      contasVencendoHojeValor:
          (json['contas_vencendo_hoje_valor'] as num?)?.toDouble() ?? 0,
      contasPagasHojeQtd: json['contas_pagas_hoje_qtd'] as int? ?? 0,
      contasPagasHojeValor:
          (json['contas_pagas_hoje_valor'] as num?)?.toDouble() ?? 0,
      fiadoRecebidoHoje:
          (json['fiado_recebido_hoje'] as num?)?.toDouble() ?? 0,
      contasMesPago: (json['contas_mes_pago'] as num?)?.toDouble() ?? 0,
      contasMesPendente:
          (json['contas_mes_pendente'] as num?)?.toDouble() ?? 0,
      serieRecebimentosMensal:
          (json['serie_recebimentos_mensal'] as List<dynamic>? ?? [])
              .map((item) =>
                  SerieMensalPonto.fromJson(item as Map<String, dynamic>))
              .toList(),
      seriePagamentosMensal:
          (json['serie_pagamentos_mensal'] as List<dynamic>? ?? [])
              .map((item) =>
                  SerieMensalPonto.fromJson(item as Map<String, dynamic>))
              .toList(),
    );
  }

  final double vendasHoje;
  final int vendasHojeQtd;
  final double vendasMes;
  final double comprasHoje;
  final double saldoCaixa;
  final double contasReceber;
  final double contasPagar;
  final int clientes;
  final int fornecedores;
  final int produtos;
  final int estoqueBaixo;

  final int contasVencidasQtd;
  final double contasVencidasValor;
  final int contasVencendoHojeQtd;
  final double contasVencendoHojeValor;
  final int contasPagasHojeQtd;
  final double contasPagasHojeValor;
  final double fiadoRecebidoHoje;
  final double contasMesPago;
  final double contasMesPendente;
  final List<SerieMensalPonto> serieRecebimentosMensal;
  final List<SerieMensalPonto> seriePagamentosMensal;

  double get ticketMedio => vendasHojeQtd == 0 ? 0 : vendasHoje / vendasHojeQtd;

  /// Quantas contas pedem atencao imediata do gerente hoje -- dispara o
  /// banner de aviso no topo do dashboard.
  int get totalAvisoVencimento => contasVencidasQtd + contasVencendoHojeQtd;

  /// Espelha os mesmos nomes de campo do backend -- usado so pra
  /// guardar no cache local (ver CacheLocal), fromJson ja le esse
  /// mesmo formato de volta.
  Map<String, dynamic> toJson() => {
    'vendas_hoje': vendasHoje,
    'vendas_hoje_qtd': vendasHojeQtd,
    'vendas_mes': vendasMes,
    'compras_hoje': comprasHoje,
    'saldo_caixa': saldoCaixa,
    'contas_receber': contasReceber,
    'contas_pagar': contasPagar,
    'clientes': clientes,
    'fornecedores': fornecedores,
    'produtos': produtos,
    'estoque_baixo': estoqueBaixo,
    'contas_vencidas_qtd': contasVencidasQtd,
    'contas_vencidas_valor': contasVencidasValor,
    'contas_vencendo_hoje_qtd': contasVencendoHojeQtd,
    'contas_vencendo_hoje_valor': contasVencendoHojeValor,
    'contas_pagas_hoje_qtd': contasPagasHojeQtd,
    'contas_pagas_hoje_valor': contasPagasHojeValor,
    'fiado_recebido_hoje': fiadoRecebidoHoje,
    'contas_mes_pago': contasMesPago,
    'contas_mes_pendente': contasMesPendente,
    'serie_recebimentos_mensal':
        serieRecebimentosMensal.map((item) => item.toJson()).toList(),
    'serie_pagamentos_mensal':
        seriePagamentosMensal.map((item) => item.toJson()).toList(),
  };
}
