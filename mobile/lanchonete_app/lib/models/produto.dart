class Produto {
  final int id;
  final String codigo;
  final String nome;
  final String? descricao;
  final String? categoria;
  final String unidade;
  final double precoVenda;
  final int estoque;
  final int estoqueMinimo;
  final bool ativo;

  Produto({
    required this.id,
    required this.codigo,
    required this.nome,
    this.descricao,
    this.categoria,
    required this.unidade,
    required this.precoVenda,
    required this.estoque,
    required this.estoqueMinimo,
    required this.ativo,
  });

  factory Produto.fromJson(Map<String, dynamic> json) {
    return Produto(
      id: json['id'] as int,
      codigo: json['codigo'] as String,
      nome: json['nome'] as String,
      descricao: json['descricao'] as String?,
      categoria: json['categoria'] as String?,
      unidade: json['unidade'] as String? ?? 'UN',
      precoVenda: (json['preco_venda'] as num).toDouble(),
      estoque: json['estoque'] as int,
      estoqueMinimo: json['estoque_minimo'] as int,
      ativo: json['ativo'] as bool,
    );
  }
}
