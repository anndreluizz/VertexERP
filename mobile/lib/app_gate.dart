import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/providers.dart';
import 'core/sessao_controller.dart';
import 'features/auth/lock_screen.dart';
import 'features/auth/login_screen.dart';
import 'features/dashboard/dashboard_screen.dart';
import 'features/server/server_setup_screen.dart';

/// Decide qual tela mostrar de acordo com o estado da sessao — troca
/// automaticamente assim que o SessaoController muda de status
/// (ex.: token expira em algum lugar do app -> volta pro login sozinho).
class AppGate extends ConsumerWidget {
  const AppGate({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final status = ref.watch(
      sessaoControllerProvider.select((s) => s.status),
    );

    return switch (status) {
      StatusSessao.carregando => const _Carregando(),
      StatusSessao.semServidor => const ServerSetupScreen(),
      StatusSessao.deslogado => const LoginScreen(),
      StatusSessao.bloqueado => const LockScreen(),
      StatusSessao.logado => const DashboardScreen(),
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
