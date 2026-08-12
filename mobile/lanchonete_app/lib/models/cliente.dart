class Cliente {
  final int id;
  final String nome;
  final String? cpfCnpj;
  final String? telefone;
  final bool ativo;

  Cliente({
    required this.id,
    required this.nome,
    this.cpfCnpj,
    this.telefone,
    required this.ativo,
  });

  factory Cliente.fromJson(Map<String, dynamic> json) {
    return Cliente(
      id: json['id'] as int,
      nome: json['nome'] as String,
      cpfCnpj: json['cpf_cnpj'] as String?,
      telefone: json['telefone'] as String?,
      ativo: json['ativo'] as bool,
    );
  }
}
