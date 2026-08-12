import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../models/movimento_fiado.dart';
import '../../models/produto_resumo.dart';
import '../../models/venda.dart';

enum PeriodoVendas { hoje, semana, mes, ano, todos }

extension PeriodoVendasRotulo on PeriodoVendas {
  String get rotulo => switch (this) {
    PeriodoVendas.hoje => 'Hoje',
    PeriodoVendas.semana => 'Semana',
    PeriodoVendas.mes => 'Mês',
    PeriodoVendas.ano => 'Ano',
    PeriodoVendas.todos => 'Todas',
  };

  bool contem(DateTime data) {
    final agora = DateTime.now();
    final hoje = DateTime(agora.year, agora.month, agora.day);

    switch (this) {
      case PeriodoVendas.hoje:
        return data.year == hoje.year &&
            data.month == hoje.month &&
            data.day == hoje.day;
      case PeriodoVendas.semana:
        return data.isAfter(hoje.subtract(const Duration(days: 7)));
      case PeriodoVendas.mes:
        return data.year == hoje.year && data.month == hoje.month;
      case PeriodoVendas.ano:
        return data.year == hoje.year;
      case PeriodoVendas.todos:
        return true;
    }
  }
}

final periodoVendasProvider = StateProvider<PeriodoVendas>(
  (ref) => PeriodoVendas.hoje,
);

final vendasProvider = FutureProvider.autoDispose<List<Venda>>((ref) async {
  final api = ref.watch(apiClientProvider);
  final resposta = await api.dio.get('/vendas/');

  final vendas = (resposta.data as List<dynamic>)
      .map((json) => Venda.fromJson(json as Map<String, dynamic>))
      .toList();

  vendas.sort((a, b) => b.data.compareTo(a.data));
  return vendas;
});

/// Mapa produto_id -> nome, usado pra mostrar o nome do produto nos
/// itens de uma venda (o endpoint de venda so devolve o id).
final produtosLookupProvider = FutureProvider.autoDispose<Map<int, String>>((
  ref,
) async {
  final api = ref.watch(apiClientProvider);
  final resposta = await api.dio.get('/produtos/');

  final produtos = (resposta.data as List<dynamic>)
      .map((json) => ProdutoResumo.fromJson(json as Map<String, dynamic>))
      .toList();

  return {for (final produto in produtos) produto.id: produto.nome};
});

/// Item da linha do tempo de "Vendas" -- uma venda de verdade ou um
/// recebimento de fiado (pagamento de uma compra a prazo já feita).
/// A tela pedia pra mostrar os dois juntos, não só as vendas.
sealed class ItemAtividadeVendas {
  DateTime get data;
}

class AtividadeVenda extends ItemAtividadeVendas {
  AtividadeVenda(this.venda);

  final Venda venda;

  @override
  DateTime get data => venda.data;
}

class AtividadeRecebimento extends ItemAtividadeVendas {
  AtividadeRecebimento(this.movimento, this.clienteNome);

  final MovimentoFiado movimento;
  final String clienteNome;

  @override
  DateTime get data => movimento.data;
}

/// Combina vendas + recebimentos de fiado (movimentos tipo PAGAMENTO)
/// numa lista só, mais recente primeiro -- os mesmos chips de período
/// da tela de Vendas já funcionam em cima disso sem mudança nenhuma,
/// já que cada item sabe devolver sua própria data.
final atividadeVendasProvider = FutureProvider.autoDispose<
  List<ItemAtividadeVendas>
>((ref) async {
  final api = ref.watch(apiClientProvider);

  final respostaVendas = await api.dio.get('/vendas/');
  final vendas = (respostaVendas.data as List<dynamic>)
      .map((json) => Venda.fromJson(json as Map<String, dynamic>))
      .toList();

  final respostaMovimentos = await api.dio.get('/fiado/movimentos');
  final recebimentos = (respostaMovimentos.data as List<dynamic>)
      .map((json) => MovimentoFiado.fromJson(json as Map<String, dynamic>))
      .where((m) => m.tipo == 'PAGAMENTO')
      .toList();

  final respostaClientes = await api.dio.get('/clientes/');
  final nomesClientes = {
    for (final json in respostaClientes.data as List<dynamic>)
      (json as Map<String, dynamic>)['id'] as int: json['nome'] as String,
  };

  final itens = <ItemAtividadeVendas>[
    ...vendas.map(AtividadeVenda.new),
    ...recebimentos.map(
      (m) => AtividadeRecebimento(
        m,
        nomesClientes[m.clienteId] ?? 'Cliente',
      ),
    ),
  ];

  itens.sort((a, b) => b.data.compareTo(a.data));
  return itens;
});
