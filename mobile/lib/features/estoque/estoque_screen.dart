import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../models/produto.dart';
import '../../theme/lista_agrupada.dart';
import '../../theme/skeleton.dart';
import '../../theme/vertex_colors.dart';
import 'cadastro_produto_screen.dart';
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
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const CadastroProdutoScreen()),
        ),
        icon: const Icon(Icons.add),
        label: const Text('Novo produto'),
      ),
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
                loading: () => const SkeletonList(),
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
                    FiltroEstoque.criticos =>
                      produtos
                          .where((p) => p.semEstoque || p.estoqueBaixo)
                          .toList(),
                    FiltroEstoque.semEstoque =>
                      produtos.where((p) => p.semEstoque).toList(),
                  };

                  if (filtrados.isEmpty) {
                    return ListView(
                      children: const [
                        SizedBox(height: 80),
                        Center(child: Text('Nenhum produto nessa condição.')),
                      ],
                    );
                  }

                  return ListView(
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                    children: [
                      CabecalhoGrupo(
                        '${filtrados.length} produto'
                        '${filtrados.length == 1 ? '' : 's'}',
                      ),
                      ListaAgrupada(
                        linhas: [
                          for (final produto in filtrados)
                            _LinhaProduto(produto: produto),
                        ],
                      ),
                    ],
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

class _LinhaProduto extends StatelessWidget {
  const _LinhaProduto({required this.produto});

  final Produto produto;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    final (String, Color)? estado = produto.semEstoque
        ? ('Sem estoque', VertexColors.erro)
        : produto.estoqueBaixo
        ? ('Abaixo do mínimo (${produto.estoqueMinimo})', VertexColors.alerta)
        : null;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  produto.nome,
                  style: tema.titleSmall,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  '${produto.codigo} · ${formatarMoeda(produto.precoVenda)}',
                  style: tema.bodySmall,
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '${produto.estoque} un.',
                style: tema.titleSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                  color: estado?.$2,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
              if (estado != null) ...[
                const SizedBox(height: 2),
                Text(
                  estado.$1,
                  style: tema.labelSmall?.copyWith(
                    color: estado.$2,
                    letterSpacing: 0,
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }
}
