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
    required this.temDocumento,
    required this.documentoNome,
    required this.temComprovantePagamento,
    required this.comprovantePagamentoNome,
    required this.formaPagamento,
    required this.bancoPagamento,
    required this.numeroTransacao,
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
      temDocumento: json['tem_documento'] as bool? ?? false,
      documentoNome: json['documento_nome'] as String?,
      temComprovantePagamento:
          json['tem_comprovante_pagamento'] as bool? ?? false,
      comprovantePagamentoNome:
          json['comprovante_pagamento_nome'] as String?,
      formaPagamento: json['forma_pagamento'] as String?,
      bancoPagamento: json['banco_pagamento'] as String?,
      numeroTransacao: json['numero_transacao'] as String?,
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
  final bool temDocumento;
  final String? documentoNome;
  final bool temComprovantePagamento;
  final String? comprovantePagamentoNome;
  final String? formaPagamento;
  final String? bancoPagamento;
  final String? numeroTransacao;
}
