import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/features/financeiro/financeiro_screen.dart';

void main() {
  test('codigo do boleto copia so os digitos', () {
    expect(codigoBoleto('23793.38128 60000.000003 00000.000400 1 84340000010000'),
        '23793381286000000000300000000400184340000010000');
    expect(codigoBoleto(null), isNull);
    expect(codigoBoleto(' - '), isNull);
  });
}
