/// Espelha backend/app/schemas/produto.py::ProdutoResponse.
class Produto {
  const Produto({
    required this.id,
    required this.codigo,
    required this.nome,
    required this.categoria,
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
      categoria: json['categoria'] as String?,
      precoVenda: (json['preco_venda'] as num).toDouble(),
      estoque: json['estoque'] as int,
      estoqueMinimo: json['estoque_minimo'] as int,
      ativo: json['ativo'] as bool,
    );
  }

  final int id;
  final String codigo;
  final String nome;
  final String? categoria;
  final double precoVenda;
  final int estoque;
  final int estoqueMinimo;
  final bool ativo;

  bool get semEstoque => estoque <= 0;
  bool get estoqueBaixo => !semEstoque && estoque <= estoqueMinimo;
}
