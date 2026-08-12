import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/providers.dart';
import 'core/sessao_controller.dart';
import 'features/auth/lock_screen.dart';
import 'features/auth/login_screen.dart';
import 'features/server/server_setup_screen.dart';
import 'home_shell.dart';

/// Depois de quanto tempo em segundo plano o app volta pedindo
/// biometria de novo (ver didChangeAppLifecycleState) — "bloqueio
/// automatico" da Fase 6. Curto de proposito: e a mesma logica de
/// autoprotecao que um app de banco costuma ter.
const _tempoLimiteBloqueio = Duration(minutes: 2);

/// Decide qual tela mostrar de acordo com o estado da sessao — troca
/// automaticamente assim que o SessaoController muda de status
/// (ex.: token expira em algum lugar do app -> volta pro login sozinho).
///
/// Tambem observa o ciclo de vida do app inteiro (unico widget que
/// sempre fica montado, nao importa qual tela esta em cima) pra travar
/// a sessao sozinho depois de muito tempo em segundo plano.
class AppGate extends ConsumerStatefulWidget {
  const AppGate({super.key});

  @override
  ConsumerState<AppGate> createState() => _AppGateState();
}

class _AppGateState extends ConsumerState<AppGate> with WidgetsBindingObserver {
  DateTime? _pausadoEm;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused) {
      _pausadoEm = DateTime.now();
      return;
    }

    if (state == AppLifecycleState.resumed) {
      final pausadoEm = _pausadoEm;
      _pausadoEm = null;

      if (pausadoEm != null &&
          DateTime.now().difference(pausadoEm) > _tempoLimiteBloqueio) {
        ref.read(sessaoControllerProvider.notifier).travarPorInatividade();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final status = ref.watch(sessaoControllerProvider.select((s) => s.status));

    return switch (status) {
      StatusSessao.carregando => const _Carregando(),
      StatusSessao.semServidor => const ServerSetupScreen(),
      StatusSessao.deslogado => const LoginScreen(),
      StatusSessao.bloqueado => const LockScreen(),
      StatusSessao.logado => const HomeShell(),
    };
  }
}

class _Carregando extends StatelessWidget {
  const _Carregando();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(body: Center(child: CircularProgressIndicator()));
  }
}
