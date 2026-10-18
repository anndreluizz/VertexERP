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

        ref.invalidate(notificacoesProvider);

        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$titulo — $corpo')));
      });

      final vigia = ref.read(vigiaNotificacoesProvider);
      _vigia = vigia;
      vigia.iniciar();
    });
  }

  VigiaNotificacoes? _vigia;

  @override
  void dispose() {
    // saiu da conta: para de consultar (evitaria 401 em loop)
    _vigia?.parar();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final naoLidas = ref.watch(naoLidasProvider);
    // Vendedor nao tem a aba Financeiro (Mais vira o indice 3); o clamp
    // cobre trocar de admin pra vendedor parado na aba Mais
    final financeiro =
        ref.watch(sessaoControllerProvider).usuario?.financeiro ?? true;
    final indice = ref
        .watch(abaSelecionadaProvider)
        .clamp(0, financeiro ? 4 : 3);

    return Scaffold(
      body: IndexedStack(
        index: indice,
        children: [
          const DashboardScreen(),
          const VendasScreen(),
          const ClientesScreen(),
          if (financeiro) const FinanceiroScreen(),
          const MaisScreen(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: indice,
        onDestinationSelected: (novoIndice) =>
            ref.read(abaSelecionadaProvider.notifier).state = novoIndice,
        destinations: [
          const NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home),
            label: 'Início',
          ),
          const NavigationDestination(
            icon: Icon(Icons.receipt_long_outlined),
            selectedIcon: Icon(Icons.receipt_long),
            label: 'Vendas',
          ),
          const NavigationDestination(
            icon: Icon(Icons.people_outline),
            selectedIcon: Icon(Icons.people),
            label: 'Clientes',
          ),
          if (financeiro)
            const NavigationDestination(
              icon: Icon(Icons.account_balance_wallet_outlined),
              selectedIcon: Icon(Icons.account_balance_wallet),
              label: 'Financeiro',
            ),
          NavigationDestination(
            icon: Badge(
              isLabelVisible: naoLidas > 0,
              label: Text(naoLidas > 99 ? '99+' : '$naoLidas'),
              child: const Icon(Icons.more_horiz),
            ),
            label: 'Mais',
          ),
        ],
      ),
    );
  }
}
