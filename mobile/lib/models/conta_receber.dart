/// Espelha backend/app/schemas/conta_receber.py::ContaReceberResponse.
class ContaReceber {
  const ContaReceber({
    required this.id,
    required this.clienteId,
    required this.vendaId,
    required this.dataEmissao,
    required this.dataVencimento,
    required this.dataRecebimento,
    required this.valor,
    required this.observacao,
    required this.status,
  });

  factory ContaReceber.fromJson(Map<String, dynamic> json) {
    return ContaReceber(
      id: json['id'] as int,
      clienteId: json['cliente_id'] as int,
      vendaId: json['venda_id'] as int?,
      dataEmissao: DateTime.parse(json['data_emissao'] as String),
      dataVencimento: DateTime.parse(json['data_vencimento'] as String),
      dataRecebimento: json['data_recebimento'] != null
          ? DateTime.parse(json['data_recebimento'] as String)
          : null,
      valor: (json['valor'] as num).toDouble(),
      observacao: json['observacao'] as String?,
      status: json['status'] as String,
    );
  }

  final int id;
  final int clienteId;
  final int? vendaId;
  final DateTime dataEmissao;
  final DateTime dataVencimento;
  final DateTime? dataRecebimento;
  final double valor;
  final String? observacao;
  final String status;
}
