class Usuario {
  const Usuario({
    required this.id,
    required this.nome,
    required this.email,
    required this.ativo,
    required this.admin,
    this.lojaId,
    this.permissoes = const [],
  });

  factory Usuario.fromJson(Map<String, dynamic> json) {
    return Usuario(
      id: json['id'] as int,
      nome: json['nome'] as String,
      email: json['email'] as String,
      ativo: json['ativo'] as bool,
      admin: json['admin'] as bool,
      lojaId: json['loja_id'] as int?,
      permissoes: (json['permissoes'] as List?)?.cast<String>() ?? const [],
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

  // admin ja' vem com o catalogo inteiro (ver User.permissoes no backend)
  final List<String> permissoes;

  /// Sem financeiro.ver = Vendedor: so' as proprias vendas/caixa, sem
  /// Financeiro nem Relatorios (o backend tambem barra).
  bool get financeiro => admin || permissoes.contains('financeiro.ver');

  /// Entrada de estoque pelo app (POST /estoque/movimentos).
  bool get podeAjustarEstoque =>
      admin || permissoes.contains('estoque.ajustar');

  String get cargo => admin
      ? 'Administrador'
      : financeiro
      ? 'Gerente'
      : 'Vendedor';
}
