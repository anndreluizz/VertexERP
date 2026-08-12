import '../models/cliente.dart';
import 'api_client.dart';

class ClienteService {
  final ApiClient client;

  ClienteService(this.client);

  Future<List<Cliente>> listar() async {
    final json = await client.get('/clientes/') as List;
    return json
        .map((e) => Cliente.fromJson(e as Map<String, dynamic>))
        .where((c) => c.ativo)
        .toList();
  }
}
