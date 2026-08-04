import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

import 'api_client.dart';

/// Push notifications (Firebase Cloud Messaging). Cada chamada aqui e
/// protegida — enquanto esta instalacao nao tiver um
/// google-services.json de verdade (ver android/app/build.gradle.kts),
/// Firebase.initializeApp() em main.dart falha silenciosamente e
/// Firebase.apps fica vazio; o resto do app continua funcionando
/// normal, so sem notificacao nenhuma.
class NotificacaoService {
  NotificacaoService(this._api);

  final ApiClient _api;

  bool get _firebaseDisponivel => Firebase.apps.isNotEmpty;

  /// Pede permissao (Android 13+ exige) e registra o token do
  /// aparelho no backend, associado ao usuario logado.
  Future<void> registrarToken() async {
    if (!_firebaseDisponivel) return;

    try {
      final mensageria = FirebaseMessaging.instance;

      final configuracao = await mensageria.requestPermission();

      if (configuracao.authorizationStatus ==
          AuthorizationStatus.denied) {
        return;
      }

      final token = await mensageria.getToken();

      if (token == null) return;

      await _api.dio.post(
        '/notificacoes/registrar-token',
        data: {'token': token, 'plataforma': 'ANDROID'},
      );
    } catch (_) {
      // Falha ao pedir permissao/token/registrar — nao trava o login
      // nem o resto do app por causa disso.
    }
  }

  /// Mensagens recebidas com o app aberto nao aparecem como
  /// notificacao do sistema sozinhas — precisa de tratamento proprio
  /// (aqui, so entrega pro callback pra tela mostrar um aviso simples).
  void ouvirMensagensEmPrimeiroPlano(
    void Function(String titulo, String corpo) aoReceber,
  ) {
    if (!_firebaseDisponivel) return;

    FirebaseMessaging.onMessage.listen((mensagem) {
      final titulo = mensagem.notification?.title;
      final corpo = mensagem.notification?.body;

      if (titulo != null && corpo != null) {
        aoReceber(titulo, corpo);
      }
    });
  }
}
