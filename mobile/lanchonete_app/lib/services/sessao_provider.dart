import 'package:flutter/foundation.dart';

import '../models/usuario.dart';
import 'api_client.dart';
import 'auth_service.dart';

class SessaoProvider extends ChangeNotifier {
  final ApiClient client = ApiClient();
  late final AuthService _authService = AuthService(client);

  Usuario? usuario;
  bool carregando = true;

  bool get configurado => client.isConfigured;
  bool get logado => usuario != null;
  bool get admin => usuario?.admin ?? false;

  Future<void> init() async {
    await client.init();
    if (client.isAuthenticated) {
      try {
        usuario = await _authService.carregarPerfil();
      } catch (_) {
        await client.clearToken();
      }
    }
    carregando = false;
    notifyListeners();
  }

  Future<void> configurarServidor(String url) async {
    await client.setBaseUrl(url);
    notifyListeners();
  }

  Future<void> login(String email, String senha) async {
    await _authService.login(email, senha);
    usuario = await _authService.carregarPerfil();
    notifyListeners();
  }

  Future<void> logout() async {
    await _authService.logout();
    usuario = null;
    notifyListeners();
  }
}
