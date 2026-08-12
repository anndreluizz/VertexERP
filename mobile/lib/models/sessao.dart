/// Espelha backend/app/schemas/refresh_token.py::SessaoResponse.
class Sessao {
  const Sessao({
    required this.id,
    required this.dispositivo,
    required this.criadoEm,
    required this.ultimoUsoEm,
  });

  factory Sessao.fromJson(Map<String, dynamic> json) {
    return Sessao(
      id: json['id'] as int,
      dispositivo: json['dispositivo'] as String?,
      criadoEm: DateTime.parse(json['criado_em'] as String),
      ultimoUsoEm: DateTime.parse(json['ultimo_uso_em'] as String),
    );
  }

  final int id;
  final String? dispositivo;
  final DateTime criadoEm;
  final DateTime ultimoUsoEm;
}
