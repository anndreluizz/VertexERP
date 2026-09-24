import 'package:flutter/material.dart';

import 'vertex_colors.dart';

/// Placeholder "shimmer" puro Flutter (sem pacote novo) -- um brilho
/// suave passando da esquerda pra direita enquanto o dado de verdade
/// nao chega, no lugar do spinner generico de sempre.
class SkeletonBox extends StatefulWidget {
  const SkeletonBox({
    super.key,
    this.width,
    this.height = 14,
    this.borderRadius = 8,
  });

  final double? width;
  final double height;
  final double borderRadius;

  @override
  State<SkeletonBox> createState() => _SkeletonBoxState();
}

class _SkeletonBoxState extends State<SkeletonBox>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final escuro = Theme.of(context).brightness == Brightness.dark;
    final base = VertexColors.borda;
    final brilho = escuro
        ? VertexColors.textoSecundario.withValues(alpha: 0.18)
        : Colors.white.withValues(alpha: 0.85);

    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return Container(
          width: widget.width,
          height: widget.height,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(widget.borderRadius),
            gradient: LinearGradient(
              begin: Alignment(-1 + _controller.value * 3, 0),
              end: Alignment(1 + _controller.value * 3, 0),
              colors: [base, brilho, base],
              stops: const [0.35, 0.5, 0.65],
            ),
          ),
        );
      },
    );
  }
}

/// Skeleton no formato do topo do Inicio (painel de vendas + quadro
/// financeiro), pra nao "pular" o layout quando o dado chega.
class SkeletonResumoHoje extends StatelessWidget {
  const SkeletonResumoHoje({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SkeletonBox(height: 176, borderRadius: 16),
        const SizedBox(height: 28),
        const SkeletonBox(width: 90, height: 15),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                for (var i = 0; i < 6; i++) ...[
                  if (i > 0) const SizedBox(height: 22),
                  const Row(
                    children: [
                      SkeletonBox(width: 110),
                      Spacer(),
                      SkeletonBox(width: 80),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ),
      ],
    );
  }
}

/// Skeleton no formato de um cartao de lista (Financeiro, Vendas...).
class SkeletonListCard extends StatelessWidget {
  const SkeletonListCard({super.key});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const SkeletonBox(width: 140, height: 15),
                const Spacer(),
                const SkeletonBox(width: 60, height: 15),
              ],
            ),
            const SizedBox(height: 10),
            const SkeletonBox(width: 90, height: 11),
          ],
        ),
      ),
    );
  }
}

class SkeletonList extends StatelessWidget {
  const SkeletonList({super.key, this.itens = 6});

  final int itens;

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: itens,
      separatorBuilder: (_, _) => const SizedBox(height: 10),
      itemBuilder: (_, _) => const SkeletonListCard(),
    );
  }
}
