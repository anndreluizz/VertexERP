import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/sessao_provider.dart';
import 'dashboard_screen.dart';
import 'pedido_screen.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _abaAtual = 0;

  @override
  Widget build(BuildContext context) {
    final admin = context.watch<SessaoProvider>().admin;

    final telas = [
      const PedidoScreen(),
      if (admin) const DashboardScreen(),
    ];

    if (_abaAtual >= telas.length) {
      _abaAtual = 0;
    }

    return Scaffold(
      body: IndexedStack(index: _abaAtual, children: telas),
      bottomNavigationBar: telas.length == 1
          ? null
          : NavigationBar(
              selectedIndex: _abaAtual,
              onDestinationSelected: (index) => setState(() => _abaAtual = index),
              destinations: const [
                NavigationDestination(icon: Icon(Icons.receipt_long), label: 'Pedidos'),
                NavigationDestination(icon: Icon(Icons.dashboard), label: 'Gerenciamento'),
              ],
            ),
    );
  }
}
