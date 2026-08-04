/// Recorte minimo de backend/app/schemas/produto.py::ProdutoResponse —
/// so o necessario pra mostrar o nome do produto num item de venda.
class ProdutoResumo {
  const ProdutoResumo({required this.id, required this.nome});

  factory ProdutoResumo.fromJson(Map<String, dynamic> json) {
    return ProdutoResumo(id: json['id'] as int, nome: json['nome'] as String);
  }

  final int id;
  final String nome;
}
