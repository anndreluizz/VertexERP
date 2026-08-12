/// Espelha backend/app/schemas/solicitacao_aprovacao.py.
class SolicitacaoAprovacao {
  const SolicitacaoAprovacao({
    required this.id,
    required this.tipo,
    required this.referenciaId,
    required this.descricao,
    required this.status,
    required this.solicitanteId,
    required this.criadoEm,
  });

  factory SolicitacaoAprovacao.fromJson(Map<String, dynamic> json) {
    return SolicitacaoAprovacao(
      id: json['id'] as int,
      tipo: json['tipo'] as String,
      referenciaId: json['referencia_id'] as int,
      descricao: json['descricao'] as String,
      status: json['status'] as String,
      solicitanteId: json['solicitante_id'] as int,
      criadoEm: DateTime.parse(json['criado_em'] as String),
    );
  }

  final int id;
  final String tipo;
  final int referenciaId;
  final String descricao;
  final String status;
  final int solicitanteId;
  final DateTime criadoEm;
}
