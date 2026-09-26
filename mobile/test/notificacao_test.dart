import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/features/notificacoes/notificacoes_provider.dart';

void main() {
  test('criado_em vem em hora local do servidor e nao e convertido', () {
    final n = Notificacao.fromJson({
      'id': 1,
      'titulo': 'Nova venda',
      'corpo': 'x',
      'lida': false,
      'criado_em': '2026-09-24T12:30:00',
    });

    expect(n.criadoEm, DateTime(2026, 9, 24, 12, 30));
  });
}
