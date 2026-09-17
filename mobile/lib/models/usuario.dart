class Usuario {
  const Usuario({
    required this.id,
    required this.nome,
    required this.email,
    required this.ativo,
    required this.admin,
    this.lojaId,
  });

  factory Usuario.fromJson(Map<String, dynamic> json) {
    return Usuario(
      id: json['id'] as int,
      nome: json['nome'] as String,
      email: json['email'] as String,
      ativo: json['ativo'] as bool,
      admin: json['admin'] as bool,
      lojaId: json['loja_id'] as int?,
    );
  }

  final int id;
  final String nome;
  final String email;
  final bool ativo;
  final bool admin;
  // null pra admin sem loja de origem fixa -- ver
  // app/auth/dependencies.resolver_loja_id no backend.
  final int? lojaId;

  String get cargo => admin ? 'Administrador' : 'Operador';
}
