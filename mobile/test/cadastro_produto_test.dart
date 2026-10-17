import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:mobile/core/api_client.dart';
import 'package:mobile/core/providers.dart';
import 'package:mobile/features/estoque/cadastro_produto_screen.dart';

/// Responde as rotas da tela e guarda os POSTs feitos.
class _ServidorFalso implements HttpClientAdapter {
  final posts = <String, Map<String, dynamic>>{};

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    ResponseBody json(Object corpo, [int status = 200]) =>
        ResponseBody.fromString(
          jsonEncode(corpo),
          status,
          headers: {
            Headers.contentTypeHeader: [Headers.jsonContentType],
          },
        );

    if (options.method == 'POST') {
      posts[options.path] = options.data as Map<String, dynamic>;
      return json({}, 201);
    }
    if (options.path.startsWith('/pdv/produto/789')) {
      return json({'id': 7, 'codigo': '0007', 'nome': 'BOLSA', 'estoque': 3});
    }
    if (options.path.startsWith('/pdv/produto/')) {
      return json({'detail': 'Produto não encontrado.'}, 404);
    }
    return json([]);
  }

  @override
  void close({bool force = false}) {}
}

Future<_ServidorFalso> _abrir(WidgetTester tester) async {
  final api = ApiClient();
  final servidor = _ServidorFalso();
  api.dio.httpClientAdapter = servidor;
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(api),
        lojaFiltroProvider.overrideWithValue(null),
      ],
      child: const MaterialApp(home: CadastroProdutoScreen()),
    ),
  );
  await tester.pumpAndSettle();
  return servidor;
}

void main() {
  testWidgets('codigo ja cadastrado vira entrada de estoque', (tester) async {
    final servidor = await _abrir(tester);

    await tester.enterText(find.byType(TextField).first, '789');
    await tester.testTextInput.receiveAction(TextInputAction.next);
    await tester.pumpAndSettle();

    expect(find.text('Produto já cadastrado'), findsOneWidget);
    await tester.enterText(find.byType(TextField).last, '5');
    await tester.tap(find.text('Adicionar'));
    await tester.pumpAndSettle();

    final entrada = servidor.posts['/estoque/movimentos']!;
    expect(entrada['produto_id'], 7);
    expect(entrada['quantidade'], 5);
    expect(entrada['tipo'], 'ENTRADA');
    expect(servidor.posts.containsKey('/produtos/'), isFalse);
  });

  testWidgets('produto novo cadastra com preco em formato BR', (tester) async {
    final servidor = await _abrir(tester);

    await tester.enterText(find.byType(TextField).first, '111');
    await tester.testTextInput.receiveAction(TextInputAction.next);
    await tester.pumpAndSettle();
    expect(find.text('Produto já cadastrado'), findsNothing);

    await tester.enterText(
      find.widgetWithText(TextField, 'Nome'),
      'bolsa azul',
    );
    await tester.enterText(
      find.widgetWithText(TextField, 'Preço de venda'),
      '1.234,50',
    );
    await tester.tap(find.text('Cadastrar'));
    await tester.pumpAndSettle();

    final produto = servidor.posts['/produtos/']!;
    expect(produto['nome'], 'BOLSA AZUL');
    expect(produto['preco_venda'], 1234.5);
    expect(produto['codigo_barras'], '111');
  });
}
