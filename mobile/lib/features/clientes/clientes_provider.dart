import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../models/cliente.dart';
import '../../models/movimento_fiado.dart';

final buscaClientesProvider = StateProvider<String>((ref) => '');

final clientesProvider = FutureProvider.autoDispose<List<Cliente>>((
  ref,
) async {
  final api = ref.watch(apiClientProvider);
  final resposta = await api.dio.get('/clientes/');

  final clientes = (resposta.data as List<dynamic>)
      .map((json) => Cliente.fromJson(json as Map<String, dynamic>))
      .where((cliente) => cliente.ativo)
      .toList();

  clientes.sort((a, b) => a.nome.compareTo(b.nome));
  return clientes;
});

final clienteProvider = FutureProvider.autoDispose.family<Cliente, int>((
  ref,
  clienteId,
) async {
  final api = ref.watch(apiClientProvider);
  final resposta = await api.dio.get('/clientes/$clienteId');
  return Cliente.fromJson(resposta.data as Map<String, dynamic>);
});

final saldoFiadoProvider = FutureProvider.autoDispose.family<double, int>((
  ref,
  clienteId,
) async {
  final api = ref.watch(apiClientProvider);
  final resposta = await api.dio.get('/fiado/saldo/$clienteId');
  return (resposta.data['saldo'] as num).toDouble();
});

final historicoFiadoProvider = FutureProvider.autoDispose
    .family<List<MovimentoFiado>, int>((ref, clienteId) async {
      final api = ref.watch(apiClientProvider);
      final resposta = await api.dio.get(
        '/fiado/movimentos/cliente/$clienteId',
      );

      final movimentos = (resposta.data as List<dynamic>)
          .map(
            (json) => MovimentoFiado.fromJson(json as Map<String, dynamic>),
          )
          .toList();

      movimentos.sort((a, b) => b.data.compareTo(a.data));
      return movimentos;
    });
