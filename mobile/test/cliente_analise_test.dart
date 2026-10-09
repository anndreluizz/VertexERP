import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/cliente_analise.dart';
import 'package:mobile/models/movimento_fiado.dart';

// Mesmos casos de frontend/tests/test_cliente_analise.py -- o celular
// tem que classificar igual ao Desktop.

final _agora = DateTime(2026, 10, 7, 12);
var _id = 0;

MovimentoFiado _mov(String tipo, double valor, int diasAtras) => MovimentoFiado(
  id: _id++,
  clienteId: 1,
  vendaId: null,
  tipo: tipo,
  valor: valor,
  descricao: null,
  formaPagamento: null,
  data: _agora.subtract(Duration(days: diasAtras)),
);

AnaliseCliente _agr(List<MovimentoFiado> movs) =>
    analisarCliente(movs, agora: _agora);

void main() {
  test('quem compra sempre e nunca paga e inadimplente', () {
    final a = _agr([_mov('COMPRA', 100, 120), _mov('COMPRA', 50, 1)]);
    expect(a.diasEmAtraso, 120);
    expect(a.status, StatusCliente.inadimplente);
  });

  test('pagamento parcial quita a compra mais antiga primeiro', () {
    final a = _agr([
      _mov('COMPRA', 100, 120),
      _mov('COMPRA', 100, 20),
      _mov('PAGAMENTO', 100, 10),
    ]);
    expect(a.diasEmAtraso, 20);
    expect(a.prazoMedioPagamento, 110);
    expect(a.inadimplente, isFalse);
    expect(a.status, StatusCliente.pagaComAtraso);
  });

  test('pagamento simbolico nao esconde divida velha', () {
    final a = _agr([_mov('COMPRA', 1000, 150), _mov('PAGAMENTO', 5, 2)]);
    expect(a.diasEmAtraso, 150);
    expect(a.status, StatusCliente.inadimplente);
  });

  test('bom pagador', () {
    final movs = <MovimentoFiado>[];
    for (var i = 0; i < 5; i++) {
      movs
        ..add(_mov('COMPRA', 50, 80 - i * 15))
        ..add(_mov('PAGAMENTO', 50, 75 - i * 15));
    }
    final a = _agr(movs);
    expect(a.prazoMedioPagamento, 5);
    expect(a.diasEmAtraso, isNull);
    expect(a.status, StatusCliente.bomPagador);
  });

  test('sem historico de pagamento nao e bom pagador', () {
    final a = _agr([_mov('COMPRA', 50, 3)]);
    expect(a.prazoMedioPagamento, isNull);
    expect(a.status, StatusCliente.emDia);
  });

  test('saldo anterior importado conta como compra', () {
    final a = _agr([_mov('COMPRA', 1744, 5)]);
    expect(a.saldoDevedor, 1744);
    expect(a.diasEmAtraso, 5);
  });

  test('haver abate a divida e quem nao deve nada e quitado', () {
    final a = _agr([_mov('COMPRA', 50, 10), _mov('HAVER', 50, 2)]);
    expect(a.saldoDevedor, 0);
    expect(a.diasEmAtraso, isNull);
    expect(a.status, StatusCliente.bomPagador);
    expect(_agr([]).status, StatusCliente.quitado);
  });

  test('analisarTodos separa por cliente', () {
    final outro = MovimentoFiado(
      id: 999,
      clienteId: 2,
      vendaId: null,
      tipo: 'COMPRA',
      valor: 30,
      descricao: null,
      formaPagamento: null,
      data: _agora,
    );
    final todos = analisarTodos([_mov('COMPRA', 10, 1), outro], agora: _agora);
    expect(todos[1]!.saldoDevedor, 10);
    expect(todos[2]!.saldoDevedor, 30);
  });
}
