import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/api_client.dart';

void main() {
  group('mensagemDeErro', () {
    test('extrai o detail do backend quando presente', () {
      final erro = DioException(
        requestOptions: RequestOptions(path: '/contas-pagar/1/pagar'),
        response: Response(
          requestOptions: RequestOptions(path: '/contas-pagar/1/pagar'),
          statusCode: 400,
          data: {'detail': 'Conta já foi paga.'},
        ),
      );

      final resultado = mensagemDeErro(erro, fallback: 'erro generico');

      expect(resultado, 'Conta já foi paga.');
    });

    test('cai pro fallback quando a resposta nao tem detail', () {
      final erro = DioException(
        requestOptions: RequestOptions(path: '/contas-pagar/1/pagar'),
        response: Response(
          requestOptions: RequestOptions(path: '/contas-pagar/1/pagar'),
          statusCode: 500,
          data: {'outra_coisa': 'sem detail aqui'},
        ),
      );

      final resultado = mensagemDeErro(erro, fallback: 'erro generico');

      expect(resultado, 'erro generico');
    });

    test('cai pro fallback quando nao ha response nenhuma (rede fora)', () {
      final erro = DioException(
        requestOptions: RequestOptions(path: '/contas-pagar/1/pagar'),
        type: DioExceptionType.connectionTimeout,
      );

      final resultado = mensagemDeErro(erro, fallback: 'erro generico');

      expect(resultado, 'erro generico');
    });

    test('cai pro fallback pra erro que nao e DioException', () {
      final resultado = mensagemDeErro(
        Exception('algo local quebrou'),
        fallback: 'erro generico',
      );

      expect(resultado, 'erro generico');
    });
  });
}
