import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../../../core/formatadores.dart';
import '../../../theme/vertex_colors.dart';

/// Grafico de rosca "pago x pendente" do mes atual -- ve de relance se
/// as contas do mes ja estao equilibradas ou se ainda falta muito pra
/// sair da conta da loja.
class GraficoPagoPendente extends StatelessWidget {
  const GraficoPagoPendente({
    super.key,
    required this.pago,
    required this.pendente,
  });

  final double pago;
  final double pendente;

  @override
  Widget build(BuildContext context) {
    final total = pago + pendente;

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Contas a pagar do mês',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 4),
            Text(
              'Pago × pendente',
              style: TextStyle(
                fontSize: 11.5,
                color: VertexColors.textoSecundario,
              ),
            ),
            const SizedBox(height: 14),
            if (total <= 0)
              Padding(
                padding: EdgeInsets.symmetric(vertical: 24),
                child: Center(
                  child: Text(
                    'Nenhuma conta neste mês.',
                    style: TextStyle(
                      fontSize: 12.5,
                      color: VertexColors.textoTerciario,
                    ),
                  ),
                ),
              )
            else
              Row(
                children: [
                  SizedBox(
                    width: 120,
                    height: 120,
                    child: PieChart(
                      PieChartData(
                        sectionsSpace: 2,
                        centerSpaceRadius: 32,
                        sections: [
                          PieChartSectionData(
                            value: pago,
                            color: VertexColors.secundaria,
                            title: '',
                            radius: 18,
                          ),
                          PieChartSectionData(
                            value: pendente,
                            color: VertexColors.alerta,
                            title: '',
                            radius: 18,
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(width: 18),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _Legenda(
                          cor: VertexColors.secundaria,
                          rotulo: 'Pago',
                          valor: pago,
                        ),
                        const SizedBox(height: 10),
                        _Legenda(
                          cor: VertexColors.alerta,
                          rotulo: 'Pendente',
                          valor: pendente,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

class _Legenda extends StatelessWidget {
  const _Legenda({
    required this.cor,
    required this.rotulo,
    required this.valor,
  });

  final Color cor;
  final String rotulo;
  final double valor;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: cor, shape: BoxShape.circle),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                rotulo,
                style: TextStyle(
                  fontSize: 11.5,
                  color: VertexColors.textoSecundario,
                ),
              ),
              Text(
                formatarMoeda(valor),
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
