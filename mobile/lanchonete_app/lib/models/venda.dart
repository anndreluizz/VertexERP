enum FormaPagamento { dinheiro, pix, debito, credito, boleto, prazo }

extension FormaPagamentoX on FormaPagamento {
  String get valor {
    switch (this) {
      case FormaPagamento.dinheiro:
        return 'DINHEIRO';
      case FormaPagamento.pix:
        return 'PIX';
      case FormaPagamento.debito:
        return 'DEBITO';
      case FormaPagamento.credito:
        return 'CREDITO';
      case FormaPagamento.boleto:
        return 'BOLETO';
      case FormaPagamento.prazo:
        return 'PRAZO';
    }
  }

  String get rotulo {
    switch (this) {
      case FormaPagamento.dinheiro:
        return 'Dinheiro';
      case FormaPagamento.pix:
        return 'Pix';
      case FormaPagamento.debito:
        return 'Débito';
      case FormaPagamento.credito:
        return 'Crédito';
      case FormaPagamento.boleto:
        return 'Boleto';
      case FormaPagamento.prazo:
        return 'A prazo';
    }
  }
}

class ItemVendaCreate {
  final int produtoId;
  final int quantidade;
  final double valorUnitario;

  ItemVendaCreate({
    required this.produtoId,
    required this.quantidade,
    required this.valorUnitario,
  });

  Map<String, dynamic> toJson() => {
        'produto_id': produtoId,
        'quantidade': quantidade,
        'valor_unitario': valorUnitario,
      };
}

class VendaCreate {
  final int? clienteId;
  final String? observacao;
  final double desconto;
  final FormaPagamento formaPagamento;
  final List<ItemVendaCreate> itens;

  VendaCreate({
    this.clienteId,
    this.observacao,
    this.desconto = 0.0,
    this.formaPagamento = FormaPagamento.dinheiro,
    required this.itens,
  });

  Map<String, dynamic> toJson() => {
        'cliente_id': clienteId,
        'observacao': observacao,
        'desconto': desconto,
        'forma_pagamento': formaPagamento.valor,
        'itens': itens.map((i) => i.toJson()).toList(),
      };
}

class VendaResponse {
  final int id;
  final double valorTotal;
  final String status;

  VendaResponse({
    required this.id,
    required this.valorTotal,
    required this.status,
  });

  factory VendaResponse.fromJson(Map<String, dynamic> json) {
    return VendaResponse(
      id: json['id'] as int,
      valorTotal: (json['valor_total'] as num).toDouble(),
      status: json['status'] as String,
    );
  }
}
