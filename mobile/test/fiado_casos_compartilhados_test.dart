import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/cliente_analise.dart';
import 'package:mobile/models/movimento_fiado.dart';

// Mesmos casos de fiado que o servidor e o PC
// (testes_compartilhados/fiado_casos.json) -- se um dos tres calcular
// diferente, o CI barra.

void main() {
  final arquivo = File('../testes_compartilhados/fiado_casos.json');
  final casos =
      (jsonDecode(arquivo.readAsStringSync()) as Map<String, dynamic>)['casos']
          as List<dynamic>;
  final agora = DateTime(2026, 10, 15, 12);

  for (final caso in casos.cast<Map<String, dynamic>>()) {
    test(caso['nome'] as String, () {
      var id = 0;
      final movs = (caso['movimentos'] as List<dynamic>).map((m) {
        final linha = m as List<dynamic>;
        return MovimentoFiado(
          id: id++,
          clienteId: 1,
          vendaId: null,
          tipo: linha[0] as String,
          valor: (linha[1] as num).toDouble(),
          descricao: null,
          formaPagamento: null,
          data: agora.subtract(Duration(days: linha[2] as int)),
        );
      }).toList();

      final a = analisarCliente(movs, agora: agora);

      expect(a.saldoDevedor, closeTo((caso['saldo'] as num).toDouble(), 0.001));
      expect(a.diasEmAtraso, caso['dias_em_atraso']);
    });
  }
}
