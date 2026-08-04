import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/providers.dart';
import 'features/clientes/clientes_screen.dart';
import 'features/dashboard/dashboard_screen.dart';
import 'features/financeiro/financeiro_screen.dart';
import 'features/mais/mais_screen.dart';
import 'features/notificacoes/notificacoes_provider.dart';
import 'features/vendas/vendas_screen.dart';

/// Casca do app depois do login: navegacao entre os modulos por baixo,
/// cada aba mantem seu proprio estado (IndexedStack), igual o
/// QStackedWidget do Desktop. "Mais" concentra os modulos usados com
/// menos frequencia (Estoque, Caixas, Relatorios, Notificacoes) pra
/// barra nao lotar conforme o roteiro completo for saindo (Perfil,
/// Configuracoes ainda vem por ai).
class HomeShell extends ConsumerStatefulWidget {
  const HomeShell({super.key});

  @override
  ConsumerState<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends ConsumerState<HomeShell> {
  int _indice = 0;

  static const _paginas = [
    DashboardScreen(),
    VendasScreen(),
    ClientesScreen(),
    FinanceiroScreen(),
    MaisScreen(),
  ];

  @override
  void initState() {
    super.initState();

    // So dispara depois que a tela ja montou (evita usar `ref`/context
    // antes da arvore de widgets estar pronta).
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final notificacoes = ref.read(notificacaoServiceProvider);

      notificacoes.registrarToken();

      notificacoes.ouvirMensagensEmPrimeiroPlano((titulo, corpo) {
        if (!mounted) return;

        ref.read(notificacoesProvider.notifier).adicionar(titulo, corpo);

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$titulo — $corpo')),
        );
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _indice, children: _paginas),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _indice,
        onDestinationSelected: (indice) => setState(() => _indice = indice),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home),
            label: 'Início',
          ),
          NavigationDestination(
            icon: Icon(Icons.receipt_long_outlined),
            selectedIcon: Icon(Icons.receipt_long),
            label: 'Vendas',
          ),
          NavigationDestination(
            icon: Icon(Icons.people_outline),
            selectedIcon: Icon(Icons.people),
            label: 'Clientes',
          ),
          NavigationDestination(
            icon: Icon(Icons.account_balance_wallet_outlined),
            selectedIcon: Icon(Icons.account_balance_wallet),
            label: 'Financeiro',
          ),
          NavigationDestination(
            icon: Icon(Icons.more_horiz),
            selectedIcon: Icon(Icons.more_horiz),
            label: 'Mais',
          ),
        ],
      ),
    );
  }
}
