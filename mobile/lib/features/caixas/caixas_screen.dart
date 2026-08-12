import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../models/caixa.dart';
import '../../theme/vertex_colors.dart';
import 'caixas_provider.dart';

String _formatarDuracao(Duration duracao) {
  final horas = duracao.inHours;
  final minutos = duracao.inMinutes % 60;

  if (horas <= 0) return '${minutos}min';
  return '${horas}h ${minutos}min';
}

class CaixasScreen extends ConsumerWidget {
  const CaixasScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final caixasAsync = ref.watch(caixasProvider);
    final operadoresAsync = ref.watch(operadoresLookupProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Caixas')),
      body: RefreshIndicator(
        onRefresh: () => ref.refresh(caixasProvider.future),
        child: caixasAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (erro, _) => ListView(
            children: const [
              SizedBox(height: 80),
              Center(child: Text('Não foi possível carregar os caixas.')),
            ],
          ),
          data: (caixas) {
            final operadores = operadoresAsync.value ?? const {};

            final abertos = caixas.where((c) => c.aberto).toList();
            final fechados = caixas.where((c) => !c.aberto).toList();

            if (caixas.isEmpty) {
              return ListView(
                children: const [
                  SizedBox(height: 80),
                  Center(child: Text('Nenhum caixa registrado ainda.')),
                ],
              );
            }

            return ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text(
                  abertos.isEmpty
                      ? 'Nenhum caixa aberto agora'
                      : '${abertos.length} caixa(s) aberto(s) agora',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 10),
                for (final caixa in abertos)
                  _CartaoCaixa(
                    caixa: caixa,
                    nomeOperador: operadores[caixa.usuarioId],
                  ),
                if (fechados.isNotEmpty) ...[
                  const SizedBox(height: 22),
                  Text(
                    'Histórico recente',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 10),
                  for (final caixa in fechados)
                    _CartaoCaixa(
                      caixa: caixa,
                      nomeOperador: operadores[caixa.usuarioId],
                    ),
                ],
              ],
            );
          },
        ),
      ),
    );
  }
}

class _CartaoCaixa extends StatelessWidget {
  const _CartaoCaixa({required this.caixa, this.nomeOperador});

  final Caixa caixa;
  final String? nomeOperador;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Container(
              width: 38,
              height: 38,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: caixa.aberto
                    ? VertexColors.sucessoClaro
                    : VertexColors.primariaClara,
                borderRadius: BorderRadius.circular(11),
              ),
              child: Icon(
                caixa.aberto
                    ? Icons.point_of_sale
                    : Icons.lock_outline,
                size: 18,
                color: caixa.aberto
                    ? VertexColors.secundaria
                    : VertexColors.primaria,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    nomeOperador ?? 'Operador #${caixa.usuarioId ?? '-'}',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  Text(
                    caixa.aberto
                        ? 'Aberto há ${_formatarDuracao(caixa.tempoAberto)}'
                        : 'Fechado em ${formatarDataHora(caixa.dataFechamento!)}',
                    style: TextStyle(
                      fontSize: 12,
                      color: VertexColors.textoSecundario,
                    ),
                  ),
                ],
              ),
            ),
            Text(
              formatarMoeda(caixa.saldoFinal),
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ],
        ),
      ),
    );
  }
}
