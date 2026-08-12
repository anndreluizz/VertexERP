import '../models/usuario.dart';
import 'api_client.dart';

class AuthService {
  final ApiClient client;

  AuthService(this.client);

  Future<void> login(String email, String senha) async {
    final json = await client.post('/auth/login', {
      'email': email,
      'senha': senha,
    });
    await client.setToken(json['access_token'] as String);
  }

  Future<Usuario> carregarPerfil() async {
    final json = await client.get('/users/me');
    final data = client.unwrap(json) as Map<String, dynamic>;
    return Usuario.fromJson(data);
  }

  Future<void> logout() async {
    await client.clearToken();
  }
}
