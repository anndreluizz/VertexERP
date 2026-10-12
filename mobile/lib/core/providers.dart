import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_client.dart';
import 'notificacao_service.dart';
import 'sessao_controller.dart';
import 'vertex_storage.dart';

final storageProvider = Provider<VertexStorage>((ref) => VertexStorage());

/// Indice da aba ativa no HomeShell (Inicio/Vendas/Clientes/Financeiro/
/// Mais) -- elevado aqui (em vez de estado local da tela) pra outras
/// telas poderem trocar de aba sozinhas, ex.: o banner de "contas
/// vencendo hoje" do dashboard levando direto pro Financeiro.
final abaSelecionadaProvider = StateProvider<int>((ref) => 0);

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());

final notificacaoServiceProvider = Provider<NotificacaoService>(
  (ref) => NotificacaoService(ref.watch(apiClientProvider)),
);

final sessaoControllerProvider =
    StateNotifierProvider<SessaoController, SessaoState>((ref) {
      final api = ref.watch(apiClientProvider);
      final storage = ref.watch(storageProvider);

      final controller = SessaoController(api, storage);

      // Ligado depois de criado — evita o ApiClient precisar conhecer
      // o SessaoController na hora de construir os dois.
      api.aoReceber401 = controller.logout;
      api.aoRenovarToken = controller.renovarToken;

      return controller;
    });

/// Lojas ativas (id, nome) pro seletor do inicio -- falhou, lista vazia
/// e o seletor some.
final lojasProvider = FutureProvider<List<({int id, String nome})>>((
  ref,
) async {
  try {
    final resposta = await ref.watch(apiClientProvider).dio.get('/lojas/');
    return [
      for (final json in resposta.data as List<dynamic>)
        if (json['ativa'] != false)
          (id: json['id'] as int, nome: json['nome'] as String),
    ];
  } catch (_) {
    return const [];
  }
});

/// Loja escolhida no seletor do inicio (null = todas).
final lojaEscolhidaProvider = StateProvider<int?>((ref) => null);

/// Loja que filtra vendas, caixas, contas, estoque e relatorios: a do
/// usuario, se ele for preso a uma loja; senao a escolhida no seletor.
final lojaFiltroProvider = Provider<int?>(
  (ref) =>
      ref.watch(sessaoControllerProvider).usuario?.lojaId ??
      ref.watch(lojaEscolhidaProvider),
);
