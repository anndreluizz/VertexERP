/// Espelha backend/app/schemas/movimento_fiado.py.
class MovimentoFiado {
  const MovimentoFiado({
    required this.id,
    required this.clienteId,
    required this.vendaId,
    required this.tipo,
    required this.valor,
    required this.descricao,
    required this.formaPagamento,
    required this.data,
  });

  factory MovimentoFiado.fromJson(Map<String, dynamic> json) {
    return MovimentoFiado(
      id: json['id'] as int,
      clienteId: json['cliente_id'] as int,
      vendaId: json['venda_id'] as int?,
      tipo: json['tipo'] as String,
      valor: (json['valor'] as num).toDouble(),
      descricao: json['descricao'] as String?,
      formaPagamento: json['forma_pagamento'] as String?,
      data: DateTime.parse(json['data'] as String),
    );
  }

  final int id;
  final int clienteId;
  final int? vendaId;
  final String tipo;
  final double valor;
  final String? descricao;
  final String? formaPagamento;
  final DateTime data;
}
