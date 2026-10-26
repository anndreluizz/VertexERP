/// Espelha backend/app/schemas/caixa.py::CaixaResponse.
class Caixa {
  const Caixa({
    required this.id,
    required this.dataAbertura,
    required this.dataFechamento,
    required this.saldoInicial,
    required this.saldoFinal,
    required this.status,
    required this.usuarioId,
    this.vencido = false,
  });

  factory Caixa.fromJson(Map<String, dynamic> json) {
    return Caixa(
      id: json['id'] as int,
      dataAbertura: DateTime.parse(json['data_abertura'] as String),
      dataFechamento: json['data_fechamento'] != null
          ? DateTime.parse(json['data_fechamento'] as String)
          : null,
      saldoInicial: (json['saldo_inicial'] as num).toDouble(),
      saldoFinal: (json['saldo_final'] as num).toDouble(),
      // opcional na leitura -- um caixa sem status nao pode derrubar a
      // lista inteira; sem status reconhecido, "aberto" abaixo cai
      // pro lado seguro (false), nunca mostra como aberto por engano.
      status: json['status'] as String? ?? 'DESCONHECIDO',
      usuarioId: json['usuario_id'] as int?,
      // aberto ha mais de 24h (regra do servidor): so' deixa fechar
      vencido: json['vencido'] as bool? ?? false,
    );
  }

  final int id;
  final DateTime dataAbertura;
  final DateTime? dataFechamento;
  final double saldoInicial;
  final double saldoFinal;
  final String status;
  final int? usuarioId;
  final bool vencido;

  bool get aberto => status == 'ABERTO';

  Duration get tempoAberto =>
      (dataFechamento ?? DateTime.now()).difference(dataAbertura);
}
