import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../models/conta_pagar.dart';
import '../../models/produto.dart';
import '../vendas/vendas_provider.dart';
import 'relatorio_dados.dart';

final relatorioPeriodoProvider = StateProvider<PeriodoVendas>(
  (ref) => PeriodoVendas.mes,
);

final relatorioProvider = FutureProvider.autoDispose<RelatorioDados>((
  ref,
) async {
  final periodo = ref.watch(relatorioPeriodoProvider);
  final api = ref.watch(apiClientProvider);
  final lojaId = ref.watch(lojaFiltroProvider);
  final filtroLoja = lojaId != null ? {'loja_id': lojaId} : null;

  // mesmo calculo do Desktop (Relatorios > Vendas): so vendas
  // finalizadas, sem limite de 100, e devolucao/troca ja descontada.
  // Antes somava a lista /vendas/ (vinham canceladas e suspensas, e so
  // as ultimas 100)
  final agora = DateTime.now();
  final hoje = DateTime(agora.year, agora.month, agora.day);
  final DateTime? inicio = switch (periodo) {
    PeriodoVendas.hoje => hoje,
    PeriodoVendas.semana => hoje.subtract(const Duration(days: 6)),
    PeriodoVendas.mes => DateTime(hoje.year, hoje.month),
    PeriodoVendas.ano => DateTime(hoje.year),
    PeriodoVendas.todos => null,
  };
  String dia(DateTime d) => d.toIso8601String().substring(0, 10);

  final relResp = await api.dio.get(
    '/relatorios/vendas',
    queryParameters: {
      'data_inicio': ?(inicio == null ? null : dia(inicio)),
      'data_fim': dia(hoje),
      'limit': 1,
      'top_produtos_limite': 1,
      ...?filtroLoja,
    },
  );
  final rel = relResp.data as Map<String, dynamic>;
  num atual(String chave) =>
      num.tryParse('${(rel[chave] as Map<String, dynamic>)['atual']}') ?? 0;

  final totalVendas = atual('quantidade_vendas').toInt();
  final valorVendas = atual('receita_total').toDouble();

  final mixPagamento = <String, double>{
    for (final f in rel['formas_pagamento'] as List<dynamic>)
      (f as Map<String, dynamic>)['forma_pagamento'] as String:
          (f['total'] as num).toDouble(),
  };

  final contasPagarResp = await api.dio.get(
    '/contas-pagar/pendentes',
    queryParameters: filtroLoja,
  );
  final contasPagarPendente = (contasPagarResp.data as List<dynamic>)
      .map((json) => ContaPagar.fromJson(json as Map<String, dynamic>))
      .fold<double>(0, (soma, conta) => soma + conta.valor);

  // "a receber" da loja e o fiado dos clientes (a tabela antiga de
  // contas a receber nao e mais usada)
  final saldosResp = await api.dio.get('/fiado/saldos');
  final contasReceberPendente = (saldosResp.data as Map<String, dynamic>).values
      .map((v) => (v as num).toDouble())
      .where((saldo) => saldo > 0)
      .fold<double>(0, (soma, saldo) => soma + saldo);

  final produtosResp = await api.dio.get(
    '/produtos/',
    queryParameters: filtroLoja,
  );
  final produtos = (produtosResp.data as List<dynamic>)
      .map((json) => Produto.fromJson(json as Map<String, dynamic>))
      .where((produto) => produto.ativo)
      .toList();

  return RelatorioDados(
    totalVendas: totalVendas,
    valorVendas: valorVendas,
    mixPagamento: mixPagamento,
    contasPagarPendente: contasPagarPendente,
    contasReceberPendente: contasReceberPendente,
    produtosCriticos: produtos.where((p) => p.estoqueBaixo).length,
    produtosSemEstoque: produtos.where((p) => p.semEstoque).length,
  );
});
