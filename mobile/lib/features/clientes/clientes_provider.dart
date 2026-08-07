import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../models/cliente.dart';
import '../../models/movimento_fiado.dart';
import '../vendas/vendas_provider.dart';

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

/// Última compra / total comprado / qtd de compras -- calculado por
/// cima da mesma lista de vendas que a aba Vendas já carrega (mesma
/// abordagem do Desktop: sem endpoint dedicado, só filtra por
/// cliente_id no que já veio).
class EstatisticasCompraCliente {
  const EstatisticasCompraCliente({
    required this.qtdCompras,
    required this.totalComprado,
    required this.ultimaCompra,
  });

  final int qtdCompras;
  final double totalComprado;
  final DateTime? ultimaCompra;
}

final estatisticasClienteProvider = FutureProvider.autoDispose
    .family<EstatisticasCompraCliente, int>((ref, clienteId) async {
      final vendas = await ref.watch(vendasProvider.future);
      final doCliente = vendas
          .where((venda) => venda.clienteId == clienteId)
          .toList();

      if (doCliente.isEmpty) {
        return const EstatisticasCompraCliente(
          qtdCompras: 0,
          totalComprado: 0,
          ultimaCompra: null,
        );
      }

      doCliente.sort((a, b) => b.data.compareTo(a.data));

      return EstatisticasCompraCliente(
        qtdCompras: doCliente.length,
        totalComprado: doCliente.fold(0.0, (soma, v) => soma + v.valorTotal),
        ultimaCompra: doCliente.first.data,
      );
    });

class ClientesActions {
  ClientesActions(this._ref);

  final Ref _ref;

  /// Registra um recebimento de fiado pra esse cliente (mesmo
  /// endpoint que o extrato/ledger usa pra pagamentos, ver backend
  /// POST /fiado/movimentos).
  Future<String?> receberPagamento(
    int clienteId,
    double valor, {
    String? descricao,
  }) async {
    try {
      final api = _ref.read(apiClientProvider);
      await api.dio.post(
        '/fiado/movimentos',
        data: {
          'cliente_id': clienteId,
          'tipo': 'PAGAMENTO',
          'valor': valor,
          'descricao': descricao,
        },
      );
      _ref.invalidate(saldoFiadoProvider(clienteId));
      _ref.invalidate(historicoFiadoProvider(clienteId));
      return null;
    } catch (_) {
      return 'Não foi possível registrar o recebimento.';
    }
  }

  /// Manda uma mensagem de texto livre pro cliente via WhatsApp (mesmo
  /// endpoint usado pelo menu "WhatsApp ▾" da ficha do cliente no
  /// Desktop -- extrato, cobrança, saldo, haver, cadastro). Devolve
  /// `true` se saiu automaticamente; `false` significa que quem chamou
  /// deve cair pro fallback manual (abrir o wa.me com o texto pronto).
  Future<bool> enviarWhatsapp(int clienteId, String texto) async {
    try {
      final api = _ref.read(apiClientProvider);
      await api.dio.post(
        '/clientes/$clienteId/whatsapp',
        data: {'texto': texto},
      );
      return true;
    } catch (_) {
      return false;
    }
  }
}

final clientesActionsProvider = Provider((ref) => ClientesActions(ref));
