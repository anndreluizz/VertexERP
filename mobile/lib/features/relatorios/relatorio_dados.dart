class RelatorioDados {
  const RelatorioDados({
    required this.totalVendas,
    required this.valorVendas,
    required this.mixPagamento,
    required this.contasPagarPendente,
    required this.contasReceberPendente,
    required this.produtosCriticos,
    required this.produtosSemEstoque,
  });

  final int totalVendas;
  final double valorVendas;

  /// forma de pagamento (DINHEIRO/PIX/...) -> valor somado no período.
  final Map<String, double> mixPagamento;

  final double contasPagarPendente;
  final double contasReceberPendente;
  final int produtosCriticos;
  final int produtosSemEstoque;

  double get ticketMedio => totalVendas == 0 ? 0 : valorVendas / totalVendas;
}
