class Usuario {
  const Usuario({
    required this.id,
    required this.nome,
    required this.email,
    required this.ativo,
    required this.admin,
  });

  factory Usuario.fromJson(Map<String, dynamic> json) {
    return Usuario(
      id: json['id'] as int,
      nome: json['nome'] as String,
      email: json['email'] as String,
      ativo: json['ativo'] as bool,
      admin: json['admin'] as bool,
    );
  }

  final int id;
  final String nome;
  final String email;
  final bool ativo;
  final bool admin;

  String get cargo => admin ? 'Administrador' : 'Operador';
}
