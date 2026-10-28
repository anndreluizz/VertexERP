import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:mobile/core/api_client.dart';
import 'package:mobile/core/providers.dart';
import 'package:mobile/features/estoque/vitrine_screen.dart';
import 'package:mobile/models/produto.dart';

Map<String, Object?> _produto(
  int id,
  String nome, {
  bool site = false,
  bool foto = true,
  String? categoria = 'ROUPA',
  int estoque = 3,
}) => {
  'id': id,
  'codigo': '000$id',
  'nome': nome,
  'categoria': categoria,
  'preco_venda': 10.0,
  'estoque': estoque,
  'estoque_minimo': 0,
  'ativo': true,
  'vitrine_publicar': site,
  'vitrine_destaque': false,
  'tem_foto': foto,
};

/// Lista os produtos e guarda os PUTs (liga/desliga no site).
class _ServidorFalso implements HttpClientAdapter {
  final puts = <String, Map<String, dynamic>>{};

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    ResponseBody json(Object corpo) => ResponseBody.fromString(
      jsonEncode(corpo),
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
    if (options.method == 'PUT') {
      puts[options.path] = options.data as Map<String, dynamic>;
      return json({});
    }
    return json([
      _produto(1, 'PERFUME NO SITE', site: true, foto: false),
      _produto(2, 'CALCA FORA DO SITE'),
    ]);
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  test('pendencias e filtros', () {
    final semNada = Produto.fromJson(
      _produto(1, 'X', site: true, foto: false, categoria: null, estoque: 0),
    );
    expect(pendenciasVitrine(semNada), [
      'sem foto',
      'sem categoria',
      'sem estoque',
    ]);
    expect(passaFiltroVitrine(semNada, FiltroVitrine.pendencias, ''), isTrue);

    final fora = Produto.fromJson(_produto(2, 'CALCA'));
    expect(passaFiltroVitrine(fora, FiltroVitrine.noSite, ''), isFalse);
    // buscando, procura em todos
    expect(passaFiltroVitrine(fora, FiltroVitrine.noSite, 'calca'), isTrue);
  });

  testWidgets('abre em "No site" e liga produto novo pelo "Todos"', (
    tester,
  ) async {
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
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: VitrineScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('PERFUME NO SITE'), findsOneWidget);
    expect(find.text('CALCA FORA DO SITE'), findsNothing);
    expect(find.text('Sem foto'), findsOneWidget);

    await tester.tap(find.text('Todos'));
    await tester.pumpAndSettle();
    // ordem alfabetica: CALCA vem primeiro, e o 1o Switch e' o "No site"
    await tester.tap(find.byType(Switch).first);
    await tester.pumpAndSettle();

    final enviado = servidor.puts['/produtos/2']!;
    expect(enviado['vitrine_publicar'], isTrue);
    expect(enviado['vitrine_destaque'], isFalse);
    expect(enviado['codigo'], '0002');

    // deixa terminar os timers do recarregamento antes de desmontar
    await tester.pump(const Duration(seconds: 5));
  });
}
