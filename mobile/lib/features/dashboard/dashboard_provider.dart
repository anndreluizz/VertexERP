import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../models/dashboard_resumo.dart';

final dashboardProvider = FutureProvider.autoDispose<DashboardResumo>((
  ref,
) async {
  final api = ref.watch(apiClientProvider);
  final resposta = await api.dio.get('/dashboard');
  return DashboardResumo.fromJson(resposta.data as Map<String, dynamic>);
});
