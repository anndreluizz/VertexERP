import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../models/venda.dart';
import '../../theme/vertex_colors.dart';
import 'vendas_provider.dart';

class VendaDetalheScreen extends ConsumerWidget {
  const VendaDetalheScreen({super.key, required this.venda});

  final Venda venda;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final produtosAsync = ref.watch(produtosLookupProvider);

    return Scaffold(
      appBar: AppBar(title: Text('Venda #${venda.id}')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    formatarMoeda(venda.valorTotal),
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    formatarDataHora(venda.data),
                    style: TextStyle(color: VertexColors.textoSecundario),
                  ),
                  const Divider(height: 28),
                  _linha(
                    context,
                    'Forma de pagamento',
                    formatarFormaPagamento(venda.formaPagamento),
                  ),
                  if (venda.formaPagamento2 != null)
                    _linha(
                      context,
                      'Segunda forma',
                      '${formatarFormaPagamento(venda.formaPagamento2)} '
                          '(${formatarMoeda(venda.valorForma2 ?? 0)})',
                    ),
                  if (venda.desconto > 0)
                    _linha(
                      context,
                      'Desconto',
                      '- ${formatarMoeda(venda.desconto)}',
                    ),
                  if (venda.observacao != null && venda.observacao!.isNotEmpty)
                    _linha(context, 'Observação', venda.observacao!),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text('Itens', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Card(
            child: produtosAsync.when(
              loading: () => const Padding(
                padding: EdgeInsets.all(24),
                child: Center(child: CircularProgressIndicator()),
              ),
              error: (erro, _) => Column(
                children: venda.itens
                    .map((item) => _linhaItem(context, item, null))
                    .toList(),
              ),
              data: (nomes) => Column(
                children: venda.itens
                    .map((item) => _linhaItem(context, item, nomes))
                    .toList(),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _linha(BuildContext context, String rotulo, String valor) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(rotulo, style: TextStyle(color: VertexColors.textoSecundario)),
          Flexible(
            child: Text(
              valor,
              textAlign: TextAlign.right,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }

  Widget _linhaItem(
    BuildContext context,
    ItemVenda item,
    Map<int, String>? nomes,
  ) {
    final nome = nomes?[item.produtoId] ?? 'Produto #${item.produtoId}';

    return Padding(
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(nome, style: const TextStyle(fontWeight: FontWeight.w600)),
                Text(
                  '${item.quantidade}x ${formatarMoeda(item.valorUnitario)}',
                  style: TextStyle(
                    fontSize: 12.5,
                    color: VertexColors.textoSecundario,
                  ),
                ),
              ],
            ),
          ),
          Text(
            formatarMoeda(item.subtotal),
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }
}
