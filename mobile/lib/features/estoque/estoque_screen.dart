import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../models/produto.dart';
import '../../theme/vertex_colors.dart';
import 'estoque_provider.dart';

enum FiltroEstoque { todos, criticos, semEstoque }

final filtroEstoqueProvider = StateProvider<FiltroEstoque>(
  (ref) => FiltroEstoque.criticos,
);

class EstoqueScreen extends ConsumerWidget {
  const EstoqueScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final filtro = ref.watch(filtroEstoqueProvider);
    final produtosAsync = ref.watch(produtosProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Estoque')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: Row(
              children: [
                ChoiceChip(
                  label: const Text('Críticos'),
                  selected: filtro == FiltroEstoque.criticos,
                  onSelected: (_) =>
                      ref.read(filtroEstoqueProvider.notifier).state =
                          FiltroEstoque.criticos,
                ),
                const SizedBox(width: 8),
                ChoiceChip(
                  label: const Text('Sem estoque'),
                  selected: filtro == FiltroEstoque.semEstoque,
                  onSelected: (_) =>
                      ref.read(filtroEstoqueProvider.notifier).state =
                          FiltroEstoque.semEstoque,
                ),
                const SizedBox(width: 8),
                ChoiceChip(
                  label: const Text('Todos'),
                  selected: filtro == FiltroEstoque.todos,
                  onSelected: (_) =>
                      ref.read(filtroEstoqueProvider.notifier).state =
                          FiltroEstoque.todos,
                ),
              ],
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => ref.refresh(produtosProvider.future),
              child: produtosAsync.when(
                loading: () =>
                    const Center(child: CircularProgressIndicator()),
                error: (erro, _) => ListView(
                  children: const [
                    SizedBox(height: 80),
                    Center(
                      child: Text('Não foi possível carregar os produtos.'),
                    ),
                  ],
                ),
                data: (produtos) {
                  final filtrados = switch (filtro) {
                    FiltroEstoque.todos => produtos,
                    FiltroEstoque.criticos => produtos
                        .where((p) => p.semEstoque || p.estoqueBaixo)
                        .toList(),
                    FiltroEstoque.semEstoque => produtos
                        .where((p) => p.semEstoque)
                        .toList(),
                  };

                  if (filtrados.isEmpty) {
                    return ListView(
                      children: const [
                        SizedBox(height: 80),
                        Center(
                          child: Text('Nenhum produto nessa condição.'),
                        ),
                      ],
                    );
                  }

                  return ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: filtrados.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 8),
                    itemBuilder: (context, indice) =>
                        _CartaoProduto(produto: filtrados[indice]),
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

class _CartaoProduto extends StatelessWidget {
  const _CartaoProduto({required this.produto});

  final Produto produto;

  @override
  Widget build(BuildContext context) {
    final (String selo, Color cor, Color fundo)? estado = produto.semEstoque
        ? ('Sem estoque', VertexColors.erro, VertexColors.erroClaro)
        : produto.estoqueBaixo
        ? ('Estoque baixo', VertexColors.alerta, VertexColors.alertaClaro)
        : null;

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    produto.nome,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '${produto.codigo} · ${formatarMoeda(produto.precoVenda)}',
                    style: TextStyle(
                      fontSize: 12.5,
                      color: VertexColors.textoSecundario,
                    ),
                  ),
                ],
              ),
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  '${produto.estoque} un.',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                if (estado != null) ...[
                  const SizedBox(height: 4),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 2,
                    ),
                    decoration: BoxDecoration(
                      color: estado.$3,
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Text(
                      estado.$1,
                      style: TextStyle(
                        fontSize: 10.5,
                        fontWeight: FontWeight.w700,
                        color: estado.$2,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }
}
