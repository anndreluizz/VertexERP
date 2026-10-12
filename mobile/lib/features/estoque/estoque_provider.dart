import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../models/produto.dart';

final produtosProvider = FutureProvider.autoDispose<List<Produto>>((
  ref,
) async {
  final api = ref.watch(apiClientProvider);
  final lojaId = ref.watch(lojaFiltroProvider);
  final resposta = await api.dio.get(
    '/produtos/',
    queryParameters: lojaId != null ? {'loja_id': lojaId} : null,
  );

  final produtos = (resposta.data as List<dynamic>)
      .map((json) => Produto.fromJson(json as Map<String, dynamic>))
      .where((produto) => produto.ativo)
      .toList();

  // criticos primeiro: sem estoque, depois estoque baixo, depois o
  // resto em ordem alfabetica
  produtos.sort((a, b) {
    int prioridade(Produto p) {
      if (p.semEstoque) return 0;
      if (p.estoqueBaixo) return 1;
      return 2;
    }

    final diferenca = prioridade(a) - prioridade(b);
    return diferenca != 0 ? diferenca : a.nome.compareTo(b.nome);
  });

  return produtos;
});
