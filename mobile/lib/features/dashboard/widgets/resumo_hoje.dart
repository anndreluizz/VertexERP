import 'package:flutter/material.dart';

import '../../../core/formatadores.dart';
import '../../../theme/vertex_colors.dart';
import '../../../theme/vertex_theme.dart';

/// Bloco de destaque do topo do Inicio -- o numero que o dono abre o app
/// pra ver (vendas de hoje) grande, e o contexto dele logo abaixo. Mesmo
/// azul-marinho da sidebar do Desktop.
class PainelVendasHoje extends StatelessWidget {
  const PainelVendasHoje({
    super.key,
    required this.vendasHoje,
    required this.qtdVendas,
    required this.ticketMedio,
    required this.vendasMes,
    required this.saldoCaixa,
  });

  final double vendasHoje;
  final int qtdVendas;
  final double ticketMedio;
  final double vendasMes;
  final double saldoCaixa;

  @override
  Widget build(BuildContext context) {
    final escuro = VertexColors.escuro;
    final fundo = escuro ? VertexColors.primariaClara : VertexColors.sidebar;
    const branco = Colors.white;
    final apagado = Colors.white.withValues(alpha: 0.64);
    final linha = Colors.white.withValues(alpha: 0.12);
    final tema = Theme.of(context).textTheme;

    final contexto = qtdVendas == 0
        ? 'Nenhuma venda ainda hoje'
        : '$qtdVendas venda${qtdVendas > 1 ? 's' : ''} · '
              'ticket médio ${formatarMoeda(ticketMedio)}';

    return Container(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 16),
      decoration: BoxDecoration(
        color: fundo,
        borderRadius: BorderRadius.circular(VertexTheme.radiusLg),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('VENDAS HOJE', style: tema.labelSmall?.copyWith(color: apagado)),
          const SizedBox(height: 6),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(
              formatarMoeda(vendasHoje),
              style: tema.displaySmall?.copyWith(color: branco),
            ),
          ),
          const SizedBox(height: 4),
          Text(contexto, style: tema.bodySmall?.copyWith(color: apagado)),
          const SizedBox(height: 16),
          Container(height: 1, color: linha),
          const SizedBox(height: 14),
          IntrinsicHeight(
            child: Row(
              children: [
                Expanded(
                  child: _Metrica(
                    rotulo: 'No mês',
                    valor: formatarMoeda(vendasMes),
                    corRotulo: apagado,
                  ),
                ),
                VerticalDivider(width: 24, thickness: 1, color: linha),
                Expanded(
                  child: _Metrica(
                    rotulo: 'Saldo em caixa',
                    valor: formatarMoeda(saldoCaixa),
                    corRotulo: apagado,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Metrica extends StatelessWidget {
  const _Metrica({
    required this.rotulo,
    required this.valor,
    required this.corRotulo,
  });

  final String rotulo;
  final String valor;
  final Color corRotulo;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(rotulo, style: tema.labelMedium?.copyWith(color: corRotulo)),
        const SizedBox(height: 3),
        FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.centerLeft,
          child: Text(
            valor,
            style: tema.titleMedium?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
    );
  }
}

/// Uma linha do quadro "Financeiro": rotulo a esquerda, valor alinhado
/// a direita (numeros tabulares), feito extrato -- em vez de um card
/// com icone colorido por metrica.
class LinhaFinanceira {
  const LinhaFinanceira({
    required this.rotulo,
    required this.valor,
    this.qtd,
    this.cor,
  });

  final String rotulo;
  final double valor;
  final int? qtd;

  /// Cor do marcador a esquerda -- null = neutro (sem marcador).
  final Color? cor;
}

class QuadroFinanceiro extends StatelessWidget {
  const QuadroFinanceiro({
    super.key,
    required this.linhas,
    required this.aoTocar,
  });

  final List<LinhaFinanceira> linhas;
  final VoidCallback aoTocar;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;

    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: aoTocar,
        child: Column(
          children: [
            for (var i = 0; i < linhas.length; i++) ...[
              if (i > 0) const Divider(indent: 16, endIndent: 16),
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 13,
                ),
                child: Row(
                  children: [
                    Container(
                      width: 3,
                      height: 18,
                      decoration: BoxDecoration(
                        color: linhas[i].cor ?? Colors.transparent,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(linhas[i].rotulo, style: tema.bodyMedium),
                    ),
                    if ((linhas[i].qtd ?? 0) > 0) ...[
                      Text('${linhas[i].qtd}×', style: tema.labelMedium),
                      const SizedBox(width: 10),
                    ],
                    Text(
                      formatarMoeda(linhas[i].valor),
                      style: tema.titleSmall?.copyWith(
                        fontWeight: FontWeight.w700,
                        fontFeatures: const [FontFeature.tabularFigures()],
                        color: linhas[i].valor == 0
                            ? VertexColors.textoTerciario
                            : null,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
