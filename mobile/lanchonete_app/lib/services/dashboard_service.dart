import '../models/dashboard_resumo.dart';
import 'api_client.dart';

class DashboardService {
  final ApiClient client;

  DashboardService(this.client);

  Future<DashboardResumo> resumo() async {
    final json = await client.get('/dashboard/');
    return DashboardResumo.fromJson(json as Map<String, dynamic>);
  }
}
