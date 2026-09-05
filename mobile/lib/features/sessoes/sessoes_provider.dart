import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';
import '../../core/providers.dart';
import '../../models/sessao.dart';

final sessoesProvider = FutureProvider.autoDispose<List<Sessao>>((ref) async {
  final api = ref.watch(apiClientProvider);
  final resposta = await api.dio.get('/auth/sessoes');

  return (resposta.data as List<dynamic>)
      .map((json) => Sessao.fromJson(json as Map<String, dynamic>))
      .toList();
});

class SessoesActions {
  SessoesActions(this._ref);

  final Ref _ref;

  Future<String?> revogar(int sessaoId) async {
    try {
      final api = _ref.read(apiClientProvider);
      await api.dio.delete('/auth/sessoes/$sessaoId');
      _ref.invalidate(sessoesProvider);
      return null;
    } catch (e) {
      return mensagemDeErro(
        e,
        fallback: 'Não foi possível encerrar essa sessão.',
      );
    }
  }
}

final sessoesActionsProvider = Provider((ref) => SessoesActions(ref));
