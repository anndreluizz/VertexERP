import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/models/caixa.dart';
import 'package:mobile/models/venda.dart';

void main() {
  group('Venda.fromJson -- parsing defensivo', () {
    final jsonBase = {
      'id': 1,
      'cliente_id': null,
      'usuario_id': 2,
      'usuario_nome': 'Fulano',
      'lucro': 5.0,
      'data': '2026-09-05T10:00:00',
      'valor_total': 100.0,
      'desconto': 0.0,
      'observacao': null,
      'status': 'FINALIZADA',
      'forma_pagamento': 'DINHEIRO',
      'forma_pagamento_2': null,
      'valor_forma_2': null,
      'itens': [
        {
          'id': 1,
          'produto_id': 10,
          'quantidade': 2,
          'valor_unitario': 50.0,
          'subtotal': 100.0,
        },
      ],
    };

    test('parseia normalmente quando todos os campos vem preenchidos', () {
      final venda = Venda.fromJson(jsonBase);

      expect(venda.status, 'FINALIZADA');
      expect(venda.formaPagamento, 'DINHEIRO');
      expect(venda.itens, hasLength(1));
    });

    test('nao quebra quando "status" vem ausente', () {
      final json = Map<String, dynamic>.from(jsonBase)..remove('status');

      final venda = Venda.fromJson(json);

      expect(venda.status, 'DESCONHECIDO');
    });

    test('nao quebra quando "forma_pagamento" vem ausente', () {
      final json = Map<String, dynamic>.from(jsonBase)
        ..remove('forma_pagamento');

      final venda = Venda.fromJson(json);

      expect(venda.formaPagamento, '');
    });

    test('nao quebra quando "itens" vem ausente -- lista vazia', () {
      final json = Map<String, dynamic>.from(jsonBase)..remove('itens');

      final venda = Venda.fromJson(json);

      expect(venda.itens, isEmpty);
    });

    test('nao quebra quando "itens" vem null -- lista vazia', () {
      final json = Map<String, dynamic>.from(jsonBase)..['itens'] = null;

      final venda = Venda.fromJson(json);

      expect(venda.itens, isEmpty);
    });
  });

  group('Caixa.fromJson -- parsing defensivo', () {
    final jsonBase = {
      'id': 1,
      'data_abertura': '2026-09-05T08:00:00',
      'data_fechamento': null,
      'saldo_inicial': 100.0,
      'saldo_final': 150.0,
      'status': 'ABERTO',
      'usuario_id': 2,
    };

    test('parseia normalmente e "aberto" reflete o status', () {
      final caixa = Caixa.fromJson(jsonBase);

      expect(caixa.status, 'ABERTO');
      expect(caixa.aberto, isTrue);
    });

    test('nao quebra quando "status" vem ausente -- cai pro lado seguro', () {
      final json = Map<String, dynamic>.from(jsonBase)..remove('status');

      final caixa = Caixa.fromJson(json);

      expect(caixa.status, 'DESCONHECIDO');
      // nunca mostra como aberto por engano so por falta do campo
      expect(caixa.aberto, isFalse);
    });
  });
}
