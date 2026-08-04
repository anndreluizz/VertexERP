import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../models/conta_pagar.dart';
import '../../models/conta_receber.dart';

final contasPagarProvider = FutureProvider.autoDispose<List<ContaPagar>>((
  ref,
) async {
  final api = ref.watch(apiClientProvider);
  final resposta = await api.dio.get('/contas-pagar/');

  final contas = (resposta.data as List<dynamic>)
      .map((json) => ContaPagar.fromJson(json as Map<String, dynamic>))
      .where((conta) => conta.status != 'CANCELADO')
      .toList();

  contas.sort((a, b) => a.dataVencimento.compareTo(b.dataVencimento));
  return contas;
});

final contasReceberProvider = FutureProvider.autoDispose<List<ContaReceber>>((
  ref,
) async {
  final api = ref.watch(apiClientProvider);
  final resposta = await api.dio.get('/contas-receber/');

  final contas = (resposta.data as List<dynamic>)
      .map((json) => ContaReceber.fromJson(json as Map<String, dynamic>))
      .where((conta) => conta.status != 'CANCELADO')
      .toList();

  contas.sort((a, b) => a.dataVencimento.compareTo(b.dataVencimento));
  return contas;
});

class FinanceiroActions {
  FinanceiroActions(this._ref);

  final Ref _ref;

  Future<String?> pagarConta(int contaId) async {
    try {
      final api = _ref.read(apiClientProvider);
      await api.dio.post('/contas-pagar/$contaId/pagar');
      _ref.invalidate(contasPagarProvider);
      return null;
    } catch (_) {
      return 'Não foi possível marcar essa conta como paga.';
    }
  }

  Future<String?> receberConta(int contaId) async {
    try {
      final api = _ref.read(apiClientProvider);
      await api.dio.post('/contas-receber/$contaId/receber');
      _ref.invalidate(contasReceberProvider);
      return null;
    } catch (_) {
      return 'Não foi possível marcar essa conta como recebida.';
    }
  }
}

final financeiroActionsProvider = Provider(
  (ref) => FinanceiroActions(ref),
);
