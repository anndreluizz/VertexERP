import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../models/conta_pagar.dart';
import '../../models/conta_receber.dart';
import '../../models/produto.dart';
import '../../models/venda.dart';
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

  final vendasResp = await api.dio.get(
    '/vendas/',
    queryParameters: filtroLoja,
  );
  final vendas = (vendasResp.data as List<dynamic>)
      .map((json) => Venda.fromJson(json as Map<String, dynamic>))
      .where((venda) => periodo.contem(venda.data))
      .toList();

  final valorVendas = vendas.fold<double>(
    0,
    (soma, venda) => soma + venda.valorTotal,
  );

  final mixPagamento = <String, double>{};

  for (final venda in vendas) {
    final valorForma2 = venda.valorForma2 ?? 0;
    final valorFormaPrincipal = venda.valorTotal - valorForma2;

    mixPagamento[venda.formaPagamento] =
        (mixPagamento[venda.formaPagamento] ?? 0) + valorFormaPrincipal;

    if (venda.formaPagamento2 != null && venda.valorForma2 != null) {
      mixPagamento[venda.formaPagamento2!] =
          (mixPagamento[venda.formaPagamento2!] ?? 0) + venda.valorForma2!;
    }
  }

  final contasPagarResp = await api.dio.get(
    '/contas-pagar/pendentes',
    queryParameters: filtroLoja,
  );
  final contasPagarPendente = (contasPagarResp.data as List<dynamic>)
      .map((json) => ContaPagar.fromJson(json as Map<String, dynamic>))
      .fold<double>(0, (soma, conta) => soma + conta.valor);

  final contasReceberResp = await api.dio.get(
    '/contas-receber/pendentes',
    queryParameters: filtroLoja,
  );
  final contasReceberPendente = (contasReceberResp.data as List<dynamic>)
      .map((json) => ContaReceber.fromJson(json as Map<String, dynamic>))
      .fold<double>(0, (soma, conta) => soma + conta.valor);

  final produtosResp = await api.dio.get(
    '/produtos/',
    queryParameters: filtroLoja,
  );
  final produtos = (produtosResp.data as List<dynamic>)
      .map((json) => Produto.fromJson(json as Map<String, dynamic>))
      .where((produto) => produto.ativo)
      .toList();

  return RelatorioDados(
    totalVendas: vendas.length,
    valorVendas: valorVendas,
    mixPagamento: mixPagamento,
    contasPagarPendente: contasPagarPendente,
    contasReceberPendente: contasReceberPendente,
    produtosCriticos: produtos.where((p) => p.estoqueBaixo).length,
    produtosSemEstoque: produtos.where((p) => p.semEstoque).length,
  );
});
