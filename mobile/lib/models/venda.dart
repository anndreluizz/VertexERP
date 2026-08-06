/// Espelha backend/app/schemas/venda.py — GET /vendas e GET /vendas/{id}.
class ItemVenda {
  const ItemVenda({
    required this.id,
    required this.produtoId,
    required this.quantidade,
    required this.valorUnitario,
    required this.subtotal,
  });

  factory ItemVenda.fromJson(Map<String, dynamic> json) {
    return ItemVenda(
      id: json['id'] as int,
      produtoId: json['produto_id'] as int,
      quantidade: json['quantidade'] as int,
      valorUnitario: (json['valor_unitario'] as num).toDouble(),
      subtotal: (json['subtotal'] as num).toDouble(),
    );
  }

  final int id;
  final int produtoId;
  final int quantidade;
  final double valorUnitario;
  final double subtotal;
}

class Venda {
  const Venda({
    required this.id,
    required this.clienteId,
    required this.usuarioId,
    required this.usuarioNome,
    required this.lucro,
    required this.data,
    required this.valorTotal,
    required this.desconto,
    required this.observacao,
    required this.status,
    required this.formaPagamento,
    required this.formaPagamento2,
    required this.valorForma2,
    required this.itens,
  });

  factory Venda.fromJson(Map<String, dynamic> json) {
    return Venda(
      id: json['id'] as int,
      clienteId: json['cliente_id'] as int?,
      usuarioId: json['usuario_id'] as int?,
      usuarioNome: json['usuario_nome'] as String?,
      lucro: (json['lucro'] as num?)?.toDouble(),
      data: DateTime.parse(json['data'] as String),
      valorTotal: (json['valor_total'] as num).toDouble(),
      desconto: (json['desconto'] as num).toDouble(),
      observacao: json['observacao'] as String?,
      status: json['status'] as String,
      formaPagamento: json['forma_pagamento'] as String,
      formaPagamento2: json['forma_pagamento_2'] as String?,
      valorForma2: (json['valor_forma_2'] as num?)?.toDouble(),
      itens: (json['itens'] as List<dynamic>)
          .map((item) => ItemVenda.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }

  final int id;
  final int? clienteId;
  final int? usuarioId;
  final String? usuarioNome;
  final double? lucro;
  final DateTime data;
  final double valorTotal;
  final double desconto;
  final String? observacao;
  final String status;
  final String formaPagamento;
  final String? formaPagamento2;
  final double? valorForma2;
  final List<ItemVenda> itens;
}
