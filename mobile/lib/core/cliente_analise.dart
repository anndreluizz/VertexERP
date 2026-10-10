import '../models/movimento_fiado.dart';

/// Classificacao de clientes calculada na hora a partir do historico do
/// fiado -- porta de frontend/services/cliente_analise.py, pra o celular
/// mostrar os mesmos selos do Desktop (Inadimplente, Bom pagador...).
/// Mudou la, muda aqui.

/// compra em aberto mais velha que isso = inadimplente (padrao do Desktop)
const prazoInadimplenciaDias = 90;

/// quem quita, em media, em ate tantos dias e' "bom pagador"
const prazoBomPagadorDias = 30;

const _epsilon = 0.009;

enum StatusCliente { inadimplente, pagaComAtraso, bomPagador, emDia, quitado }

extension StatusClienteInfo on StatusCliente {
  String get rotulo => switch (this) {
    StatusCliente.inadimplente => 'Inadimplente',
    StatusCliente.pagaComAtraso => 'Paga com atraso',
    StatusCliente.bomPagador => 'Bom pagador',
    StatusCliente.emDia => 'Em dia',
    StatusCliente.quitado => 'Quitado',
  };
}

class AnaliseCliente {
  const AnaliseCliente({
    required this.saldoDevedor,
    required this.qtdCompras,
    required this.totalComprado,
    required this.ultimaMovimentacao,
    required this.diasEmAtraso,
    required this.prazoMedioPagamento,
    this.diasDesdeUltimoPagamento,
  });

  final double saldoDevedor;
  final int qtdCompras;
  final double totalComprado;
  final DateTime? ultimaMovimentacao;

  /// idade (dias) da compra mais antiga ainda nao paga; null sem divida
  final int? diasEmAtraso;

  /// dias que o cliente leva, em media (ponderado pelo valor), pra
  /// quitar uma compra; null se nunca quitou nada
  final int? prazoMedioPagamento;

  /// null se nunca pagou
  final int? diasDesdeUltimoPagamento;

  bool get devendo => saldoDevedor > _epsilon;

  /// compra velha em aberto e nada pago dentro do prazo -- quem esta
  /// pagando (mesmo em parcelas) nao e' inadimplente
  bool get inadimplente =>
      diasEmAtraso != null &&
      diasEmAtraso! > prazoInadimplenciaDias &&
      (diasDesdeUltimoPagamento == null ||
          diasDesdeUltimoPagamento! > prazoInadimplenciaDias);

  bool get bomPagador =>
      prazoMedioPagamento != null &&
      prazoMedioPagamento! <= prazoBomPagadorDias &&
      (diasEmAtraso == null || diasEmAtraso! <= prazoBomPagadorDias) &&
      !inadimplente;

  bool get pagaComAtraso =>
      prazoMedioPagamento != null &&
      prazoMedioPagamento! > prazoBomPagadorDias &&
      !inadimplente;

  /// Mesma prioridade do status_financeiro do Desktop, com "Quitado"
  /// separado de "Em dia" (no celular a diferenca importa na lista).
  StatusCliente get status {
    if (inadimplente) return StatusCliente.inadimplente;
    if (bomPagador) return StatusCliente.bomPagador;
    if (pagaComAtraso) return StatusCliente.pagaComAtraso;
    return devendo ? StatusCliente.emDia : StatusCliente.quitado;
  }

  static const vazia = AnaliseCliente(
    saldoDevedor: 0,
    qtdCompras: 0,
    totalComprado: 0,
    ultimaMovimentacao: null,
    diasEmAtraso: null,
    prazoMedioPagamento: null,
  );
}

int _diasAte(DateTime data, DateTime agora) {
  // nunca negativo: data no futuro (engano no seletor) conta como hoje
  final dias = agora.difference(data).inDays;
  return dias < 0 ? 0 : dias;
}

/// [movimentos] = so os do cliente, em qualquer ordem. HAVER abate a
/// divida igual pagamento (mesma conta do saldo no backend).
AnaliseCliente analisarCliente(
  List<MovimentoFiado> movimentos, {
  DateTime? agora,
}) {
  final hoje = agora ?? DateTime.now();

  final compras = movimentos.where((m) => m.tipo == 'COMPRA').toList()
    ..sort((a, b) => a.data.compareTo(b.data));
  final abatimentos =
      movimentos
          .where((m) => m.tipo == 'PAGAMENTO' || m.tipo == 'HAVER')
          .toList()
        ..sort((a, b) => a.data.compareTo(b.data));

  final totalComprado = compras.fold<double>(0, (s, m) => s + m.valor);
  final totalAbatido = abatimentos.fold<double>(0, (s, m) => s + m.valor);
  final saldo = totalComprado - totalAbatido;

  // FIFO: cada pagamento quita as compras mais antigas primeiro, como
  // um caderno de fiado
  final abertas = [
    for (final c in compras) [c.data, c.valor],
  ];
  var somaValor = 0.0;
  var somaValorDias = 0.0;
  var i = 0;

  for (final pagamento in abatimentos) {
    var valor = pagamento.valor;
    while (valor > _epsilon && i < abertas.length) {
      final dataCompra = abertas[i][0] as DateTime;
      final resto = abertas[i][1] as double;
      final abatido = resto < valor ? resto : valor;
      somaValor += abatido;
      final dias = pagamento.data.difference(dataCompra).inDays;
      somaValorDias += abatido * (dias < 0 ? 0 : dias);
      abertas[i][1] = resto - abatido;
      valor -= abatido;
      if ((abertas[i][1] as double) <= _epsilon) i++;
    }
  }

  final maisAntigaAberta = i < abertas.length
      ? abertas[i][0] as DateTime
      : null;

  DateTime? ultima;
  for (final m in movimentos) {
    if (ultima == null || m.data.isAfter(ultima)) ultima = m.data;
  }

  return AnaliseCliente(
    saldoDevedor: saldo,
    qtdCompras: compras.length,
    totalComprado: totalComprado,
    ultimaMovimentacao: ultima,
    diasEmAtraso: saldo > _epsilon && maisAntigaAberta != null
        ? _diasAte(maisAntigaAberta, hoje)
        : null,
    prazoMedioPagamento: somaValor > 0
        ? (somaValorDias / somaValor).round()
        : null,
    diasDesdeUltimoPagamento: abatimentos.isEmpty
        ? null
        : _diasAte(abatimentos.last.data, hoje),
  );
}

/// Analisa todos os clientes de uma vez a partir da lista completa de
/// movimentos (GET /fiado/movimentos).
Map<int, AnaliseCliente> analisarTodos(
  List<MovimentoFiado> movimentos, {
  DateTime? agora,
}) {
  final porCliente = <int, List<MovimentoFiado>>{};
  for (final m in movimentos) {
    porCliente.putIfAbsent(m.clienteId, () => []).add(m);
  }
  return {
    for (final MapEntry(key: id, value: movs) in porCliente.entries)
      id: analisarCliente(movs, agora: agora),
  };
}
