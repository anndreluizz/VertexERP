import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'app_gate.dart';
import 'theme/vertex_theme.dart';

void main() {
  runApp(const ProviderScope(child: VertexManagerApp()));
}

final _router = GoRouter(
  routes: [
    GoRoute(path: '/', builder: (context, state) => const AppGate()),
  ],
);

class VertexManagerApp extends StatelessWidget {
  const VertexManagerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Vertex Manager',
      debugShowCheckedModeBanner: false,
      theme: VertexTheme.claro,
      darkTheme: VertexTheme.escuro,
      themeMode: ThemeMode.system,
      routerConfig: _router,
    );
  }
}
