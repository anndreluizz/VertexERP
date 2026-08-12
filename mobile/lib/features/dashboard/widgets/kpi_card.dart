import 'package:flutter/material.dart';

import '../../../theme/vertex_colors.dart';

class KpiCard extends StatelessWidget {
  const KpiCard({
    super.key,
    required this.rotulo,
    required this.valor,
    required this.icone,
    required this.cor,
    this.selo,
  });

  final String rotulo;
  final String valor;
  final IconData icone;
  final Color cor;
  final String? selo;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 34,
                  height: 34,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: cor.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(icone, size: 17, color: cor),
                ),
                const Spacer(),
                if (selo != null)
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 7,
                      vertical: 2,
                    ),
                    decoration: BoxDecoration(
                      color: VertexColors.erroClaro,
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Text(
                      selo!,
                      style: const TextStyle(
                        fontSize: 10.5,
                        fontWeight: FontWeight.w700,
                        color: VertexColors.erro,
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              rotulo,
              style: TextStyle(
                fontSize: 12,
                color: VertexColors.textoSecundario,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 3),
            FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Text(
                valor,
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontSize: 19,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
