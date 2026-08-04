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

  double get ticketMedio =>
      vendasHojeQtd == 0 ? 0 : vendasHoje / vendasHojeQtd;
}
