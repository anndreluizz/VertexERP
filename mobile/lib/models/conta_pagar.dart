/// Espelha backend/app/schemas/conta_pagar.py::ContaPagarResponse.
class ContaPagar {
  const ContaPagar({
    required this.id,
    required this.dataEmissao,
    required this.dataVencimento,
    required this.dataPagamento,
    required this.valor,
    required this.descricao,
    required this.categoria,
    required this.observacao,
    required this.numeroBoleto,
    required this.status,
  });

  factory ContaPagar.fromJson(Map<String, dynamic> json) {
    return ContaPagar(
      id: json['id'] as int,
      dataEmissao: DateTime.parse(json['data_emissao'] as String),
      dataVencimento: DateTime.parse(json['data_vencimento'] as String),
      dataPagamento: json['data_pagamento'] != null
          ? DateTime.parse(json['data_pagamento'] as String)
          : null,
      valor: (json['valor'] as num).toDouble(),
      descricao: json['descricao'] as String?,
      categoria: json['categoria'] as String?,
      observacao: json['observacao'] as String?,
      numeroBoleto: json['numero_boleto'] as String?,
      status: json['status'] as String,
    );
  }

  final int id;
  final DateTime dataEmissao;
  final DateTime dataVencimento;
  final DateTime? dataPagamento;
  final double valor;
  final String? descricao;
  final String? categoria;
  final String? observacao;
  final String? numeroBoleto;
  final String status;
}
