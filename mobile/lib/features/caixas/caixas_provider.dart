import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../models/caixa.dart';
import '../../models/usuario.dart';

final caixasProvider = FutureProvider.autoDispose<List<Caixa>>((ref) async {
  final api = ref.watch(apiClientProvider);
  final resposta = await api.dio.get('/caixa/historico');

  final caixas = (resposta.data as List<dynamic>)
      .map((json) => Caixa.fromJson(json as Map<String, dynamic>))
      .toList();

  // abertos primeiro, depois os mais recentes
  caixas.sort((a, b) {
    if (a.aberto != b.aberto) return a.aberto ? -1 : 1;
    return b.dataAbertura.compareTo(a.dataAbertura);
  });

  return caixas;
});

/// Mapa usuario_id -> nome, pra mostrar quem esta em cada caixa. So
/// funciona pra quem é admin (endpoint é restrito) — se falhar, as
/// telas caem pro fallback "Operador #id" sem quebrar.
final operadoresLookupProvider = FutureProvider.autoDispose<Map<int, String>>(
  (ref) async {
    final api = ref.watch(apiClientProvider);

    try {
      final resposta = await api.dio.get('/users/');
      final lista = (resposta.data['data'] as List<dynamic>)
          .map((json) => Usuario.fromJson(json as Map<String, dynamic>))
          .toList();

      return {for (final usuario in lista) usuario.id: usuario.nome};
    } catch (_) {
      return {};
    }
  },
);
