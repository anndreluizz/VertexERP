import 'dart:async';

import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';

/// Espelha backend/app/schemas/notificacao.py::NotificacaoResponse.
class Notificacao {
  const Notificacao({
    required this.id,
    required this.titulo,
    required this.corpo,
    required this.lida,
    required this.criadoEm,
  });

  factory Notificacao.fromJson(Map<String, dynamic> json) {
    return Notificacao(
      id: json['id'] as int,
      titulo: json['titulo'] as String? ?? '',
      corpo: json['corpo'] as String? ?? '',
      lida: json['lida'] as bool? ?? false,
      // backend grava em hora local (datetime.now), sem fuso no JSON
      criadoEm: DateTime.parse(json['criado_em'] as String),
    );
  }

  final int id;
  final String titulo;
  final String corpo;
  final bool lida;
  final DateTime criadoEm;
}

/// Historico gravado no servidor (vendas, fiado, contas...) -- o mesmo
/// que o Desktop mostra no sino.
final notificacoesProvider = FutureProvider.autoDispose<List<Notificacao>>((
  ref,
) async {
  final api = ref.watch(apiClientProvider);
  final resposta = await api.dio.get(
    '/notificacoes/',
    queryParameters: {'limit': 50},
  );

  return (resposta.data as List<dynamic>)
      .map((json) => Notificacao.fromJson(json as Map<String, dynamic>))
      .toList();
});

/// Contador do selo na aba "Mais" -- atualizado pelo [VigiaNotificacoes].
final naoLidasProvider = StateProvider<int>((ref) => 0);

Future<void> marcarTodasLidas(WidgetRef ref) async {
  await ref
      .read(apiClientProvider)
      .dio
      .post('/notificacoes/marcar-todas-lidas');
  ref.read(naoLidasProvider.notifier).state = 0;
}

/// Sem push de verdade (Firebase nao configurado), o app pergunta ao
/// servidor de tempos em tempos enquanto esta aberto/em segundo plano e
/// mostra na barra do celular o que chegou de novo.
///
/// ponytail: polling a cada 30s so enquanto o processo do app vive --
/// com o app fechado nada chega; push de verdade exige configurar o
/// Firebase (google-services.json + FIREBASE_CREDENTIALS_PATH).
class VigiaNotificacoes {
  VigiaNotificacoes(this._ref);

  static const _intervalo = Duration(seconds: 30);

  final Ref _ref;
  final _plugin = FlutterLocalNotificationsPlugin();
  Timer? _timer;

  /// Maior id ja visto -- so o que vier acima dele vira alerta. Null ate
  /// a primeira consulta, que so marca a linha de base (nao dispara
  /// alerta de tudo que ja existia antes de abrir o app).
  int? _ultimoId;

  Future<void> iniciar() async {
    if (_timer != null) return;

    await _plugin.initialize(
      settings: const InitializationSettings(
        android: AndroidInitializationSettings('@mipmap/ic_launcher'),
      ),
    );
    await _plugin
        .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin
        >()
        ?.requestNotificationsPermission();

    await verificar();
    _timer = Timer.periodic(_intervalo, (_) => verificar());
  }

  void parar() {
    _timer?.cancel();
    _timer = null;
  }

  Future<void> verificar() async {
    try {
      final api = _ref.read(apiClientProvider);

      final contagem = await api.dio.get('/notificacoes/nao-lidas');
      _ref.read(naoLidasProvider.notifier).state =
          contagem.data['nao_lidas'] as int? ?? 0;

      final resposta = await api.dio.get(
        '/notificacoes/',
        queryParameters: {'limit': 20},
      );
      final recentes = (resposta.data as List<dynamic>)
          .map((json) => Notificacao.fromJson(json as Map<String, dynamic>))
          .toList();

      final maiorId = recentes.isEmpty
          ? 0
          : recentes.map((n) => n.id).reduce((a, b) => a > b ? a : b);

      if (_ultimoId == null) {
        _ultimoId = maiorId;
        return;
      }

      final novas = recentes.where((n) => n.id > _ultimoId!).toList();
      _ultimoId = maiorId > _ultimoId! ? maiorId : _ultimoId;

      if (novas.isEmpty) return;

      _ref.invalidate(notificacoesProvider);

      for (final n in novas.reversed) {
        await _plugin.show(
          id: n.id,
          title: n.titulo,
          body: n.corpo,
          notificationDetails: const NotificationDetails(
            android: AndroidNotificationDetails(
              'movimentos',
              'Vendas e movimentos',
              channelDescription: 'Vendas, fiado, pagamentos e contas da loja',
              importance: Importance.high,
              priority: Priority.high,
            ),
          ),
        );
      }
    } catch (_) {
      // sem rede/servidor fora -- tenta de novo no proximo ciclo
    }
  }
}

final vigiaNotificacoesProvider = Provider<VigiaNotificacoes>((ref) {
  final vigia = VigiaNotificacoes(ref);
  ref.onDispose(vigia.parar);
  return vigia;
});
