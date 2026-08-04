import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../models/venda.dart';
import '../../theme/vertex_colors.dart';
import 'venda_detalhe_screen.dart';
import 'vendas_provider.dart';

class VendasScreen extends ConsumerWidget {
  const VendasScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final periodo = ref.watch(periodoVendasProvider);
    final vendasAsync = ref.watch(vendasProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Vendas')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: PeriodoVendas.values.map((valor) {
                  final selecionado = valor == periodo;
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(valor.rotulo),
                      selected: selecionado,
                      onSelected: (_) =>
                          ref.read(periodoVendasProvider.notifier).state =
                              valor,
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => ref.refresh(vendasProvider.future),
              child: vendasAsync.when(
                loading: () =>
                    const Center(child: CircularProgressIndicator()),
                error: (erro, _) => ListView(
                  children: const [
                    SizedBox(height: 80),
                    Center(
                      child: Text('Não foi possível carregar as vendas.'),
                    ),
                  ],
                ),
                data: (vendas) {
                  final filtradas = vendas
                      .where((v) => periodo.contem(v.data))
                      .toList();

                  if (filtradas.isEmpty) {
                    return ListView(
                      children: const [
                        SizedBox(height: 80),
                        Center(
                          child: Text('Nenhuma venda nesse período.'),
                        ),
                      ],
                    );
                  }

                  return ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: filtradas.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 10),
                    itemBuilder: (context, indice) {
                      final venda = filtradas[indice];
                      return _CartaoVenda(venda: venda);
                    },
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _CartaoVenda extends StatelessWidget {
  const _CartaoVenda({required this.venda});

  final Venda venda;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(
            builder: (context) => VendaDetalheScreen(venda: venda),
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                width: 40,
                height: 40,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: VertexColors.sucessoClaro,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(
                  Icons.receipt_long_outlined,
                  color: VertexColors.secundaria,
                  size: 20,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Venda #${venda.id}',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${formatarDataHora(venda.data)} · '
                      '${formatarFormaPagamento(venda.formaPagamento)}',
                      style: TextStyle(
                        fontSize: 12.5,
                        color: VertexColors.textoSecundario,
                      ),
                    ),
                  ],
                ),
              ),
              Text(
                formatarMoeda(venda.valorTotal),
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
