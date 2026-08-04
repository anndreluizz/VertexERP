import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../models/cliente.dart';
import '../../models/movimento_fiado.dart';
import '../../theme/vertex_colors.dart';
import 'clientes_provider.dart';

class ClienteDetalheScreen extends ConsumerWidget {
  const ClienteDetalheScreen({super.key, required this.clienteId});

  final int clienteId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final clienteAsync = ref.watch(clienteProvider(clienteId));

    return Scaffold(
      appBar: AppBar(title: const Text('Ficha do cliente')),
      body: clienteAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (erro, _) =>
            const Center(child: Text('Não foi possível carregar o cliente.')),
        data: (cliente) => _Ficha(cliente: cliente),
      ),
    );
  }
}

class _Ficha extends ConsumerWidget {
  const _Ficha({required this.cliente});

  final Cliente cliente;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final saldoAsync = ref.watch(saldoFiadoProvider(cliente.id));
    final historicoAsync = ref.watch(historicoFiadoProvider(cliente.id));

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(saldoFiadoProvider(cliente.id));
        ref.invalidate(historicoFiadoProvider(cliente.id));
        await ref.read(historicoFiadoProvider(cliente.id).future);
      },
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      CircleAvatar(
                        radius: 26,
                        backgroundColor: VertexColors.primariaClara,
                        child: Text(
                          cliente.nome.isEmpty
                              ? '?'
                              : cliente.nome[0].toUpperCase(),
                          style: const TextStyle(
                            color: VertexColors.primaria,
                            fontWeight: FontWeight.w700,
                            fontSize: 18,
                          ),
                        ),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              cliente.nome,
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                            Text(
                              'Cliente desde ${formatarData(cliente.criadoEm)}',
                              style: TextStyle(
                                fontSize: 12.5,
                                color: VertexColors.textoSecundario,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const Divider(height: 28),
                  if (cliente.telefone != null)
                    _linhaContato(
                      Icons.phone_outlined,
                      cliente.telefone!,
                    ),
                  if (cliente.email != null)
                    _linhaContato(Icons.mail_outline, cliente.email!),
                  if (cliente.enderecoCompleto.isNotEmpty)
                    _linhaContato(
                      Icons.location_on_outlined,
                      cliente.enderecoCompleto,
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _CartaoValor(
                  rotulo: 'Limite de crédito',
                  valor: cliente.limiteCredito != null
                      ? formatarMoeda(cliente.limiteCredito!)
                      : '—',
                  cor: VertexColors.primaria,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: saldoAsync.when(
                  loading: () => const _CartaoValor(
                    rotulo: 'Saldo devedor',
                    valor: '...',
                    cor: VertexColors.alerta,
                  ),
                  error: (erro, _) => const _CartaoValor(
                    rotulo: 'Saldo devedor',
                    valor: '—',
                    cor: VertexColors.alerta,
                  ),
                  data: (saldo) => _CartaoValor(
                    rotulo: 'Saldo devedor',
                    valor: formatarMoeda(saldo),
                    cor: saldo > 0
                        ? VertexColors.erro
                        : VertexColors.secundaria,
                    destaque:
                        cliente.limiteCredito != null &&
                        saldo > cliente.limiteCredito!,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Text(
            'Histórico financeiro',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          historicoAsync.when(
            loading: () => const Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: CircularProgressIndicator()),
            ),
            error: (erro, _) => const Padding(
              padding: EdgeInsets.all(16),
              child: Text('Não foi possível carregar o histórico.'),
            ),
            data: (movimentos) {
              if (movimentos.isEmpty) {
                return const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('Nenhuma movimentação registrada.'),
                );
              }

              return Card(
                child: Column(
                  children: [
                    for (final movimento in movimentos)
                      _linhaMovimento(context, movimento),
                  ],
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _linhaContato(IconData icone, String texto) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(icone, size: 17, color: VertexColors.textoTerciario),
          const SizedBox(width: 10),
          Expanded(child: Text(texto)),
        ],
      ),
    );
  }

  Widget _linhaMovimento(BuildContext context, MovimentoFiado movimento) {
    final compra = movimento.tipo == 'COMPRA';

    return Padding(
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          Icon(
            compra ? Icons.arrow_upward : Icons.arrow_downward,
            size: 17,
            color: compra ? VertexColors.erro : VertexColors.secundaria,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  movimento.descricao ??
                      (compra ? 'Compra a prazo' : 'Pagamento'),
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                Text(
                  formatarData(movimento.data),
                  style: TextStyle(
                    fontSize: 12,
                    color: VertexColors.textoSecundario,
                  ),
                ),
              ],
            ),
          ),
          Text(
            '${compra ? '+' : '-'} ${formatarMoeda(movimento.valor)}',
            style: TextStyle(
              fontWeight: FontWeight.w700,
              color: compra ? VertexColors.erro : VertexColors.secundaria,
            ),
          ),
        ],
      ),
    );
  }
}

class _CartaoValor extends StatelessWidget {
  const _CartaoValor({
    required this.rotulo,
    required this.valor,
    required this.cor,
    this.destaque = false,
  });

  final String rotulo;
  final String valor;
  final Color cor;
  final bool destaque;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      color: destaque ? VertexColors.erroClaro : null,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              rotulo,
              style: TextStyle(
                fontSize: 11.5,
                color: VertexColors.textoSecundario,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              valor,
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w800,
                color: cor,
              ),
            ),
            if (destaque) ...[
              const SizedBox(height: 2),
              const Text(
                'Acima do limite',
                style: TextStyle(fontSize: 10.5, color: VertexColors.erro),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
