import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:mobile/core/api_client.dart';
import 'package:mobile/core/providers.dart';
import 'package:mobile/core/sessao_controller.dart';
import 'package:mobile/features/estoque/estoque_screen.dart';
import 'package:mobile/models/usuario.dart';

/// Lista dois produtos e guarda os POSTs feitos.
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
    Map<String, Object?> produto(int id, String codigo, String nome) => {
      'id': id,
      'codigo': codigo,
      'nome': nome,
      'categoria': null,
      'preco_venda': 10.0,
      'estoque': 12,
      'estoque_minimo': 0,
      'ativo': true,
    };
    return json([
      produto(7, '0007', 'BOLSA AZUL'),
      produto(8, '7891000', 'CADERNO'),
    ]);
  }

  @override
  void close({bool force = false}) {}
}

Future<_ServidorFalso> _abrir(
  WidgetTester tester, {
  required List<String> permissoes,
}) async {
  final api = ApiClient();
  final servidor = _ServidorFalso();
  api.dio.httpClientAdapter = servidor;
  final container = ProviderContainer(
    overrides: [
      apiClientProvider.overrideWithValue(api),
      lojaFiltroProvider.overrideWithValue(null),
    ],
  );
  addTearDown(container.dispose);
  // ignore: invalid_use_of_protected_member, invalid_use_of_visible_for_testing_member
  container.read(sessaoControllerProvider.notifier).state = SessaoState(
    status: StatusSessao.logado,
    usuario: Usuario(
      id: 2,
      nome: 'Vendedora',
      email: 'v@loja.com',
      ativo: true,
      admin: false,
      permissoes: permissoes,
    ),
  );
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(home: EstoqueScreen()),
    ),
  );
  await tester.pumpAndSettle();
  return servidor;
}

void main() {
  testWidgets('busca acha produto fora dos criticos e toque soma estoque', (
    tester,
  ) async {
    final servidor = await _abrir(tester, permissoes: ['estoque.ajustar']);

    // filtro padrao e' "Criticos": nenhum dos dois aparece
    expect(find.text('BOLSA AZUL'), findsNothing);
    await tester.enterText(find.byType(TextField), 'bolsa');
    await tester.pumpAndSettle();
    expect(find.text('CADERNO'), findsNothing);

    await tester.tap(find.text('BOLSA AZUL'));
    await tester.pumpAndSettle();
    expect(find.text('Adicionar ao estoque'), findsOneWidget);
    await tester.enterText(find.byType(TextField).last, '4');
    await tester.tap(find.text('Adicionar'));
    await tester.pumpAndSettle();

    final entrada = servidor.posts['/estoque/movimentos']!;
    expect(entrada['produto_id'], 7);
    expect(entrada['quantidade'], 4);
    expect(entrada['tipo'], 'ENTRADA');
  });

  testWidgets('sem estoque.ajustar o toque nao abre nada', (tester) async {
    await _abrir(tester, permissoes: const []);

    await tester.enterText(find.byType(TextField), '7891');
    await tester.pumpAndSettle();
    await tester.tap(find.text('CADERNO'));
    await tester.pumpAndSettle();

    expect(find.text('Adicionar ao estoque'), findsNothing);
  });
}
