import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../models/conta_pagar.dart';
import '../../models/conta_receber.dart';
import '../../theme/vertex_colors.dart';
import 'financeiro_provider.dart';

class FinanceiroScreen extends StatelessWidget {
  const FinanceiroScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Financeiro'),
          bottom: const TabBar(
            tabs: [
              Tab(text: 'A Pagar'),
              Tab(text: 'A Receber'),
            ],
          ),
        ),
        body: const TabBarView(
          children: [_AbaContasPagar(), _AbaContasReceber()],
        ),
      ),
    );
  }
}

/// Vencido ou vencendo em ate 1 dia esquenta a cor — mesmo criterio
/// usado na tela de Contas a Pagar do Desktop.
Color _corVencimento(DateTime vencimento, bool resolvida) {
  if (resolvida) return VertexColors.textoSecundario;

  final dias = vencimento.difference(DateTime.now()).inDays;
  return dias <= 1 ? VertexColors.erro : VertexColors.texto;
}

class _AbaContasPagar extends ConsumerWidget {
  const _AbaContasPagar();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final contasAsync = ref.watch(contasPagarProvider);

    return RefreshIndicator(
      onRefresh: () => ref.refresh(contasPagarProvider.future),
      child: contasAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (erro, _) => ListView(
          children: const [
            SizedBox(height: 80),
            Center(child: Text('Não foi possível carregar as contas.')),
          ],
        ),
        data: (contas) {
          if (contas.isEmpty) {
            return ListView(
              children: const [
                SizedBox(height: 80),
                Center(child: Text('Nenhuma conta a pagar.')),
              ],
            );
          }

          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: contas.length,
            separatorBuilder: (_, _) => const SizedBox(height: 10),
            itemBuilder: (context, indice) =>
                _CartaoContaPagar(conta: contas[indice]),
          );
        },
      ),
    );
  }
}

class _CartaoContaPagar extends ConsumerWidget {
  const _CartaoContaPagar({required this.conta});

  final ContaPagar conta;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final paga = conta.status == 'PAGO';

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          conta.descricao ?? 'Despesa',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                      ),
                      Text(
                        formatarMoeda(conta.valor),
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ],
                  ),
                  const SizedBox(height: 3),
                  Text(
                    'Vencimento: ${formatarData(conta.dataVencimento)}',
                    style: TextStyle(
                      fontWeight: FontWeight.w600,
                      fontSize: 12.5,
                      color: _corVencimento(conta.dataVencimento, paga),
                    ),
                  ),
                  if (!paga) ...[
                    const SizedBox(height: 10),
                    Align(
                      alignment: Alignment.centerRight,
                      child: OutlinedButton(
                        onPressed: () async {
                          final erro = await ref
                              .read(financeiroActionsProvider)
                              .pagarConta(conta.id);

                          if (erro != null && context.mounted) {
                            ScaffoldMessenger.of(
                              context,
                            ).showSnackBar(SnackBar(content: Text(erro)));
                          }
                        },
                        child: const Text('Marcar como paga'),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _AbaContasReceber extends ConsumerWidget {
  const _AbaContasReceber();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final contasAsync = ref.watch(contasReceberProvider);

    return RefreshIndicator(
      onRefresh: () => ref.refresh(contasReceberProvider.future),
      child: contasAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (erro, _) => ListView(
          children: const [
            SizedBox(height: 80),
            Center(child: Text('Não foi possível carregar as contas.')),
          ],
        ),
        data: (contas) {
          if (contas.isEmpty) {
            return ListView(
              children: const [
                SizedBox(height: 80),
                Center(child: Text('Nenhuma conta a receber.')),
              ],
            );
          }

          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: contas.length,
            separatorBuilder: (_, _) => const SizedBox(height: 10),
            itemBuilder: (context, indice) =>
                _CartaoContaReceber(conta: contas[indice]),
          );
        },
      ),
    );
  }
}

class _CartaoContaReceber extends ConsumerWidget {
  const _CartaoContaReceber({required this.conta});

  final ContaReceber conta;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final recebida = conta.status == 'RECEBIDO';

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Cliente #${conta.clienteId}',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                Text(
                  formatarMoeda(conta.valor),
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ],
            ),
            const SizedBox(height: 3),
            Text(
              'Vencimento: ${formatarData(conta.dataVencimento)}',
              style: TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: 12.5,
                color: _corVencimento(conta.dataVencimento, recebida),
              ),
            ),
            if (!recebida) ...[
              const SizedBox(height: 10),
              Align(
                alignment: Alignment.centerRight,
                child: OutlinedButton(
                  onPressed: () async {
                    final erro = await ref
                        .read(financeiroActionsProvider)
                        .receberConta(conta.id);

                    if (erro != null && context.mounted) {
                      ScaffoldMessenger.of(
                        context,
                      ).showSnackBar(SnackBar(content: Text(erro)));
                    }
                  },
                  child: const Text('Marcar como recebida'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
