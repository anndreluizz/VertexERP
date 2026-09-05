import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';
import '../../core/providers.dart';
import '../../models/solicitacao_aprovacao.dart';

final aprovacoesPendentesProvider =
    FutureProvider.autoDispose<List<SolicitacaoAprovacao>>((ref) async {
      final api = ref.watch(apiClientProvider);
      final resposta = await api.dio.get('/aprovacoes/pendentes');

      return (resposta.data as List<dynamic>)
          .map(
            (json) => SolicitacaoAprovacao.fromJson(
              json as Map<String, dynamic>,
            ),
          )
          .toList();
    });

class AprovacoesActions {
  AprovacoesActions(this._ref);

  final Ref _ref;

  Future<String?> aprovar(int solicitacaoId) async {
    try {
      final api = _ref.read(apiClientProvider);
      await api.dio.post('/aprovacoes/$solicitacaoId/aprovar');
      _ref.invalidate(aprovacoesPendentesProvider);
      return null;
    } catch (e) {
      return mensagemDeErro(
        e,
        fallback: 'Não foi possível aprovar esse pedido.',
      );
    }
  }

  Future<String?> rejeitar(int solicitacaoId) async {
    try {
      final api = _ref.read(apiClientProvider);
      await api.dio.post('/aprovacoes/$solicitacaoId/rejeitar');
      _ref.invalidate(aprovacoesPendentesProvider);
      return null;
    } catch (e) {
      return mensagemDeErro(
        e,
        fallback: 'Não foi possível rejeitar esse pedido.',
      );
    }
  }
}

final aprovacoesActionsProvider = Provider((ref) => AprovacoesActions(ref));
