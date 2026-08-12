import '../models/venda.dart';
import 'api_client.dart';

class VendaService {
  final ApiClient client;

  VendaService(this.client);

  Future<VendaResponse> criar(VendaCreate venda) async {
    final json = await client.post('/vendas/', venda.toJson());
    return VendaResponse.fromJson(json as Map<String, dynamic>);
  }
}
