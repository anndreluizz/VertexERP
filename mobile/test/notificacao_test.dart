import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/features/notificacoes/notificacoes_provider.dart';

void main() {
  test('criado_em sem fuso vem do backend em UTC e vira hora local', () {
    final n = Notificacao.fromJson({
      'id': 1,
      'titulo': 'Nova venda',
      'corpo': 'x',
      'lida': false,
      'criado_em': '2026-09-24T12:30:00',
    });

    expect(n.criadoEm, DateTime.utc(2026, 9, 24, 12, 30).toLocal());
  });

  test('criado_em que ja traz fuso nao e convertido de novo', () {
    final n = Notificacao.fromJson({
      'id': 2,
      'titulo': 'x',
      'corpo': 'x',
      'lida': true,
      'criado_em': '2026-09-24T12:30:00Z',
    });

    expect(n.criadoEm, DateTime.utc(2026, 9, 24, 12, 30).toLocal());
  });
}
