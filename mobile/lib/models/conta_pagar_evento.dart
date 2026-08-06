/// Espelha backend/app/schemas/conta_pagar.py::ContaPagarEventoResponse
/// -- uma linha da auditoria de uma despesa (quem fez o que, quando).
class ContaPagarEvento {
  const ContaPagarEvento({
    required this.id,
    required this.tipo,
    required this.usuarioNome,
    required this.dispositivo,
    required this.detalhes,
    required this.data,
  });

  factory ContaPagarEvento.fromJson(Map<String, dynamic> json) {
    return ContaPagarEvento(
      id: json['id'] as int,
      tipo: json['tipo'] as String,
      usuarioNome: json['usuario_nome'] as String?,
      dispositivo: json['dispositivo'] as String?,
      detalhes: json['detalhes'] as String?,
      data: DateTime.parse(json['data'] as String),
    );
  }

  final int id;
  final String tipo;
  final String? usuarioNome;
  final String? dispositivo;
  final String? detalhes;
  final DateTime data;

  String get rotulo => switch (tipo) {
    'CRIADA' => 'Despesa criada',
    'DOCUMENTO_ANEXADO' => 'Boleto anexado',
    'PAGA' => 'Marcada como paga',
    'COMPROVANTE_ANEXADO' => 'Comprovante anexado',
    'COMPROVANTE_TROCADO' => 'Comprovante trocado',
    'CANCELAMENTO_SOLICITADO' => 'Cancelamento solicitado',
    'CANCELADA' => 'Despesa cancelada',
    _ => tipo,
  };
}
