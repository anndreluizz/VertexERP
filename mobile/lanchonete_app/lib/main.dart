import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'screens/home_shell.dart';
import 'screens/login_screen.dart';
import 'screens/servidor_config_screen.dart';
import 'services/sessao_provider.dart';

void main() {
  runApp(const LanchoneteApp());
}

class LanchoneteApp extends StatelessWidget {
  const LanchoneteApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => SessaoProvider()..init(),
      child: MaterialApp(
        title: 'Lanchonete',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepOrange),
          useMaterial3: true,
        ),
        home: const _Raiz(),
      ),
    );
  }
}

class _Raiz extends StatelessWidget {
  const _Raiz();

  @override
  Widget build(BuildContext context) {
    final sessao = context.watch<SessaoProvider>();

    if (sessao.carregando) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (!sessao.configurado) {
      return const ServidorConfigScreen();
    }
    if (!sessao.logado) {
      return const LoginScreen();
    }
    return const HomeShell();
  }
}
