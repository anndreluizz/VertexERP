import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'app_gate.dart';
import 'theme/vertex_colors.dart';
import 'theme/vertex_theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  try {
    await Firebase.initializeApp();
  } catch (_) {
    // Sem google-services.json real ainda (ver
    // android/app/build.gradle.kts) — comportamento esperado ate o
    // projeto Firebase ser configurado; o app segue normal, so sem
    // notificacao push.
  }

  runApp(const ProviderScope(child: VertexManagerApp()));
}

final _router = GoRouter(
  routes: [GoRoute(path: '/', builder: (context, state) => const AppGate())],
);

class VertexManagerApp extends StatelessWidget {
  const VertexManagerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Vertex ERP',
      debugShowCheckedModeBanner: false,
      theme: VertexTheme.claro,
      darkTheme: VertexTheme.escuro,
      themeMode: ThemeMode.system,
      routerConfig: _router,
      builder: (context, child) {
        final escuro =
            MediaQuery.platformBrightnessOf(context) == Brightness.dark;
        VertexColors.aplicar(escuro: escuro);

        // ponytail: as telas leem VertexColors direto (sem depender do
        // Theme), entao ao trocar claro/escuro a arvore toda e' remontada
        // pela key -- perde estado de rolagem/abas nessa hora, o que e'
        // raro; migrar pra ThemeExtension se isso incomodar.
        return KeyedSubtree(key: ValueKey(escuro), child: child!);
      },
    );
  }
}
