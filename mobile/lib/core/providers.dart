import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_client.dart';
import 'sessao_controller.dart';
import 'vertex_storage.dart';

final storageProvider = Provider<VertexStorage>((ref) => VertexStorage());

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());

final sessaoControllerProvider =
    StateNotifierProvider<SessaoController, SessaoState>((ref) {
      final api = ref.watch(apiClientProvider);
      final storage = ref.watch(storageProvider);

      final controller = SessaoController(api, storage);

      // Ligado depois de criado — evita o ApiClient precisar conhecer
      // o SessaoController na hora de construir os dois.
      api.aoReceber401 = controller.logout;

      return controller;
    });
