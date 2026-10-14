import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:printing/printing.dart';

import '../../core/formatadores.dart';
import '../../core/privacidade.dart';
import '../../theme/componentes.dart';
import '../../core/providers.dart';
import '../../theme/vertex_colors.dart';
import '../vendas/vendas_provider.dart';
import 'relatorio_dados.dart';
import 'relatorio_pdf.dart';
import 'relatorio_provider.dart';

class RelatoriosScreen extends ConsumerStatefulWidget {
  const RelatoriosScreen({super.key});

  @override
  ConsumerState<RelatoriosScreen> createState() => _RelatoriosScreenState();
}

class _RelatoriosScreenState extends ConsumerState<RelatoriosScreen> {
  bool _exportando = false;

  Future<void> _exportarPdf(RelatorioDados dados) async {
    setState(() => _exportando = true);

    try {
      final nomeLoja =
          ref.read(sessaoControllerProvider).nomeLoja ?? 'Vertex ERP';
      final periodo = ref.read(relatorioPeriodoProvider);

      final bytes = await gerarPdfRelatorio(
        dados: dados,
        nomeLoja: nomeLoja,
        rotuloPeriodo: periodo.rotulo,
      );

      await Printing.sharePdf(
        bytes: bytes,
        filename: 'relatorio_vertex_erp.pdf',
      );
    } finally {
      if (mounted) setState(() => _exportando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final periodo = ref.watch(relatorioPeriodoProvider);
    final relatorioAsync = ref.watch(relatorioProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Relatórios'),
        actions: const [BotaoOlhoValores()],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: PeriodoVendas.values.map((valor) {
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(valor.rotulo),
                      selected: valor == periodo,
                      onSelected: (_) =>
                          ref.read(relatorioPeriodoProvider.notifier).state =
                              valor,
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
          Expanded(
            child: relatorioAsync.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (erro, _) => const Center(
                child: Text('Não foi possível carregar o relatório.'),
              ),
              data: (dados) => RefreshIndicator(
                onRefresh: () => ref.refresh(relatorioProvider.future),
                child: ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    IntrinsicHeight(
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Expanded(
                            child: _cartao(
                              context,
                              'Vendas',
                              '${dados.totalVendas}',
                              moedaTela(dados.valorVendas),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: _cartao(
                              context,
                              'Ticket médio',
                              moedaTela(dados.ticketMedio),
                              null,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 18),
                    Text(
                      'Mix de pagamento',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: dados.mixPagamento.isEmpty
                            ? Text(
                                'Nenhuma venda nesse período.',
                                style: TextStyle(
                                  color: VertexColors.textoSecundario,
                                ),
                              )
                            : Column(
                                children: dados.mixPagamento.entries.map((
                                  entrada,
                                ) {
                                  return Padding(
                                    padding: const EdgeInsets.symmetric(
                                      vertical: 4,
                                    ),
                                    child: Row(
                                      mainAxisAlignment:
                                          MainAxisAlignment.spaceBetween,
                                      children: [
                                        Text(
                                          formatarFormaPagamento(entrada.key),
                                        ),
                                        Text(
                                          moedaTela(entrada.value),
                                          style: const TextStyle(
                                            fontWeight: FontWeight.w700,
                                          ),
                                        ),
                                      ],
                                    ),
                                  );
                                }).toList(),
                              ),
                      ),
                    ),
                    const SizedBox(height: 18),
                    Text(
                      'Financeiro e estoque',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          children: [
                            _linhaResumo(
                              'Contas a pagar pendentes',
                              moedaTela(dados.contasPagarPendente),
                              VertexColors.erro,
                            ),
                            _linhaResumo(
                              'Contas a receber pendentes',
                              moedaTela(dados.contasReceberPendente),
                              VertexColors.alerta,
                            ),
                            _linhaResumo(
                              'Produtos em alerta de estoque',
                              '${dados.produtosCriticos}',
                              VertexColors.alerta,
                            ),
                            _linhaResumo(
                              'Produtos sem estoque',
                              '${dados.produtosSemEstoque}',
                              VertexColors.erro,
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),
                    ElevatedButton.icon(
                      onPressed: _exportando ? null : () => _exportarPdf(dados),
                      icon: _exportando
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Icon(Icons.picture_as_pdf_outlined),
                      label: const Text('Exportar / compartilhar PDF'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _cartao(
    BuildContext context,
    String rotulo,
    String valorPrincipal,
    String? valorSecundario,
  ) {
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              rotulo,
              style: TextStyle(
                fontSize: 11.5,
                fontWeight: FontWeight.w600,
                color: VertexColors.textoSecundario,
              ),
            ),
            const SizedBox(height: 4),
            Text(valorPrincipal, style: Theme.of(context).textTheme.titleLarge),
            if (valorSecundario != null)
              Text(
                valorSecundario,
                style: TextStyle(
                  fontSize: 12,
                  color: VertexColors.textoSecundario,
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _linhaResumo(String rotulo, String valor, Color cor) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Expanded(child: Text(rotulo)),
          Text(
            valor,
            style: TextStyle(fontWeight: FontWeight.w700, color: cor),
          ),
        ],
      ),
    );
  }
}
