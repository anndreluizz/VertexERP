import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/features/financeiro/financeiro_screen.dart';

void main() {
  test('copiar Pix no formato que o app do banco aceita', () {
    const copiaECola =
        '00020126580014br.gov.bcb.pix0136123e4567-e12b-12d1-a456-4266554400005204000053039865406150.005802BR5913FULANO DE TAL6008BRASILIA62070503***6304ABCD';

    expect(textoPixParaCopiar(copiaECola), copiaECola);
    expect(textoPixParaCopiar(' maria@email.com '), 'maria@email.com');
    expect(textoPixParaCopiar('529.982.247-25'), '52998224725');
    expect(textoPixParaCopiar('12.345.678/0001-95'), '12345678000195');
    expect(textoPixParaCopiar('(97) 99902-3190'), '+5597999023190');
    expect(textoPixParaCopiar('+55 97 99902-3190'), '+5597999023190');
    expect(textoPixParaCopiar(null), isNull);
    expect(textoPixParaCopiar('  '), isNull);
  });
}
