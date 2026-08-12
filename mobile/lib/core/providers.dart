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
