import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../../../core/formatadores.dart';
import '../../../models/dashboard_resumo.dart';
import '../../../theme/vertex_colors.dart';

/// Grafico de barras dos ultimos 6 meses -- reaproveitado tanto pro
/// grafico de recebimentos quanto o de pagamentos (mesmo formato de
/// dado, so muda o titulo/cor).
class GraficoSerieMensal extends StatelessWidget {
  const GraficoSerieMensal({
    super.key,
    required this.titulo,
    required this.subtitulo,
    required this.pontos,
    required this.cor,
  });

  final String titulo;
  final String subtitulo;
  final List<SerieMensalPonto> pontos;
  final Color cor;

  @override
  Widget build(BuildContext context) {
    final maior = pontos.fold<double>(
      0,
      (atual, ponto) => ponto.valor > atual ? ponto.valor : atual,
    );

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(18, 18, 18, 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              titulo,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 4),
            Text(
              subtitulo,
              style: TextStyle(
                fontSize: 11.5,
                color: VertexColors.textoSecundario,
              ),
            ),
            const SizedBox(height: 16),
            if (maior <= 0)
              Padding(
                padding: EdgeInsets.symmetric(vertical: 24),
                child: Center(
                  child: Text(
                    'Sem movimento nos últimos meses.',
                    style: TextStyle(
                      fontSize: 12.5,
                      color: VertexColors.textoTerciario,
                    ),
                  ),
                ),
              )
            else
              SizedBox(
                height: 140,
                child: BarChart(
                  BarChartData(
                    maxY: maior * 1.2,
                    gridData: const FlGridData(show: false),
                    borderData: FlBorderData(show: false),
                    titlesData: FlTitlesData(
                      leftTitles: const AxisTitles(
                        sideTitles: SideTitles(showTitles: false),
                      ),
                      rightTitles: const AxisTitles(
                        sideTitles: SideTitles(showTitles: false),
                      ),
                      topTitles: const AxisTitles(
                        sideTitles: SideTitles(showTitles: false),
                      ),
                      bottomTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          reservedSize: 22,
                          getTitlesWidget: (valor, meta) {
                            final indice = valor.toInt();
                            if (indice < 0 || indice >= pontos.length) {
                              return const SizedBox.shrink();
                            }
                            return Padding(
                              padding: const EdgeInsets.only(top: 6),
                              child: Text(
                                pontos[indice].rotuloCurto,
                                style: TextStyle(
                                  fontSize: 10.5,
                                  color: VertexColors.textoTerciario,
                                ),
                              ),
                            );
                          },
                        ),
                      ),
                    ),
                    barTouchData: BarTouchData(
                      touchTooltipData: BarTouchTooltipData(
                        getTooltipItem: (group, groupIndex, rod, rodIndex) {
                          return BarTooltipItem(
                            formatarMoeda(rod.toY),
                            const TextStyle(
                              color: Colors.white,
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                            ),
                          );
                        },
                      ),
                    ),
                    barGroups: [
                      for (var i = 0; i < pontos.length; i++)
                        BarChartGroupData(
                          x: i,
                          barRods: [
                            BarChartRodData(
                              toY: pontos[i].valor,
                              color: cor,
                              width: 16,
                              borderRadius: BorderRadius.circular(4),
                            ),
                          ],
                        ),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
