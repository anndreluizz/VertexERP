import 'package:flutter_test/flutter_test.dart';

import 'package:lanchonete_app/models/produto.dart';
import 'package:lanchonete_app/models/venda.dart';

void main() {
  test('Produto.fromJson lê os campos da API', () {
    final produto = Produto.fromJson({
      'id': 1,
      'codigo': 'P001',
      'nome': 'X-Burger',
      'descricao': null,
      'categoria': 'Lanches',
      'unidade': 'UN',
      'preco_custo': 5.0,
      'preco_venda': 12.5,
      'estoque': 10,
      'estoque_minimo': 2,
      'ativo': true,
    });

    expect(produto.nome, 'X-Burger');
    expect(produto.precoVenda, 12.5);
    expect(produto.ativo, isTrue);
  });

  test('VendaCreate.toJson monta o payload esperado pela API', () {
    final venda = VendaCreate(
      clienteId: 3,
      desconto: 2.5,
      formaPagamento: FormaPagamento.pix,
      itens: [
        ItemVendaCreate(produtoId: 1, quantidade: 2, valorUnitario: 12.5),
      ],
    );

    final json = venda.toJson();

    expect(json['cliente_id'], 3);
    expect(json['desconto'], 2.5);
    expect(json['forma_pagamento'], 'PIX');
    expect(json['itens'], [
      {'produto_id': 1, 'quantidade': 2, 'valor_unitario': 12.5},
    ]);
  });
}
