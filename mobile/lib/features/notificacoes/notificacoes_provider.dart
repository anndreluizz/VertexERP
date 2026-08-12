import 'package:flutter_riverpod/flutter_riverpod.dart';

class NotificacaoRecebida {
  const NotificacaoRecebida({
    required this.titulo,
    required this.corpo,
    required this.recebidaEm,
  });

  final String titulo;
  final String corpo;
  final DateTime recebidaEm;
}

/// So guarda o que chegou com o app aberto nesta sessao — nao e um
/// historico persistido no servidor (isso ficaria pra uma versao
/// futura, se fizer falta).
class NotificacoesController extends StateNotifier<List<NotificacaoRecebida>> {
  NotificacoesController() : super(const []);

  void adicionar(String titulo, String corpo) {
    state = [
      NotificacaoRecebida(
        titulo: titulo,
        corpo: corpo,
        recebidaEm: DateTime.now(),
      ),
      ...state,
    ];
  }
}

final notificacoesProvider =
    StateNotifierProvider<NotificacoesController, List<NotificacaoRecebida>>(
      (ref) => NotificacoesController(),
    );
