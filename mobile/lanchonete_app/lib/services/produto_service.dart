import '../models/produto.dart';
import 'api_client.dart';

class ProdutoService {
  final ApiClient client;

  ProdutoService(this.client);

  Future<List<Produto>> listar() async {
    final json = await client.get('/produtos/') as List;
    return json
        .map((e) => Produto.fromJson(e as Map<String, dynamic>))
        .where((p) => p.ativo)
        .toList();
  }
}
