import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/cache_local.dart';
import '../../core/providers.dart';
import '../../models/dashboard_resumo.dart';

const _chaveCache = 'dashboard';

/// Envelope em volta do DashboardResumo pra tela saber se o que esta
/// mostrando veio da rede agora ou e o ultimo dado bom salvo (ver
/// CacheLocal) — a rede caiu, mas o app nao fica de tela vazia por isso.
class DashboardCarregado {
  const DashboardCarregado({
    required this.resumo,
    required this.deCache,
    required this.atualizadoEm,
  });

  final DashboardResumo resumo;
  final bool deCache;
  final DateTime atualizadoEm;
}

final dashboardProvider = FutureProvider.autoDispose<DashboardCarregado>((
  ref,
) async {
  final api = ref.watch(apiClientProvider);
  final lojaId = ref.watch(sessaoControllerProvider).usuario?.lojaId;

  try {
    final resposta = await api.dio.get(
      '/dashboard',
      queryParameters: lojaId != null ? {'loja_id': lojaId} : null,
    );
    final resumo = DashboardResumo.fromJson(
      resposta.data as Map<String, dynamic>,
    );

    final agora = DateTime.now();
    // nao espera terminar de escrever pra devolver o resultado -- so
    // guarda pra proxima vez que a rede falhar.
    unawaited(CacheLocal.salvar(_chaveCache, jsonEncode(resumo.toJson())));

    return DashboardCarregado(
      resumo: resumo,
      deCache: false,
      atualizadoEm: agora,
    );
  } catch (erro) {
    final guardado = await CacheLocal.ler(_chaveCache);

    // sem cache nenhum ainda (primeira vez que abre o app sem rede) --
    // nao tem o que mostrar, propaga o erro original pra tela de "tentar
    // de novo" de sempre.
    if (guardado == null) rethrow;

    final (valorJson, atualizadoEm) = guardado;

    return DashboardCarregado(
      resumo: DashboardResumo.fromJson(
        jsonDecode(valorJson) as Map<String, dynamic>,
      ),
      deCache: true,
      atualizadoEm: atualizadoEm,
    );
  }
});
