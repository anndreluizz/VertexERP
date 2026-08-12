/// Espelha backend/app/schemas/cliente.py::ClienteResponse.
class Cliente {
  const Cliente({
    required this.id,
    required this.nome,
    required this.cpfCnpj,
    required this.email,
    required this.telefone,
    required this.endereco,
    required this.cidade,
    required this.estado,
    required this.ativo,
    required this.criadoEm,
    required this.dataNascimento,
    required this.limiteCredito,
    required this.temFoto,
  });

  factory Cliente.fromJson(Map<String, dynamic> json) {
    return Cliente(
      id: json['id'] as int,
      nome: json['nome'] as String,
      cpfCnpj: json['cpf_cnpj'] as String?,
      email: json['email'] as String?,
      telefone: json['telefone'] as String?,
      endereco: json['endereco'] as String?,
      cidade: json['cidade'] as String?,
      estado: json['estado'] as String?,
      ativo: json['ativo'] as bool,
      criadoEm: DateTime.parse(json['criado_em'] as String),
      dataNascimento: json['data_nascimento'] != null
          ? DateTime.parse(json['data_nascimento'] as String)
          : null,
      limiteCredito: (json['limite_credito'] as num?)?.toDouble(),
      temFoto: json['tem_foto'] as bool? ?? false,
    );
  }

  final int id;
  final String nome;
  final String? cpfCnpj;
  final String? email;
  final String? telefone;
  final String? endereco;
  final String? cidade;
  final String? estado;
  final bool ativo;
  final DateTime criadoEm;
  final DateTime? dataNascimento;
  final double? limiteCredito;
  final bool temFoto;

  String get enderecoCompleto {
    final partes = [
      endereco,
      cidade,
      estado,
    ].where((p) => p != null && p.isNotEmpty);
    return partes.isEmpty ? '' : partes.join(', ');
  }
}
