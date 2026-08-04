import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../core/providers.dart';
import '../../theme/vertex_colors.dart';
import 'dashboard_provider.dart';
import 'widgets/kpi_card.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  String _saudacao() {
    final hora = DateTime.now().hour;
    if (hora < 12) return 'Bom dia';
    if (hora < 18) return 'Boa tarde';
    return 'Boa noite';
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sessao = ref.watch(sessaoControllerProvider);
    final resumoAsync = ref.watch(dashboardProvider);

    final usuario = sessao.usuario;
    final primeiroNome = usuario?.nome.split(' ').first ?? '';

    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () => ref.refresh(dashboardProvider.future),
          child: CustomScrollView(
            slivers: [
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 12, 20, 4),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Container(
                                  width: 8,
                                  height: 8,
                                  decoration: const BoxDecoration(
                                    color: VertexColors.secundaria,
                                    shape: BoxShape.circle,
                                  ),
                                ),
                                const SizedBox(width: 6),
                                Text(
                                  sessao.nomeLoja ?? 'Vertex ERP',
                                  style:
                                      Theme.of(
                                        context,
                                      ).textTheme.titleMedium,
                                ),
                              ],
                            ),
                            const SizedBox(height: 2),
                            Text(
                              '${_saudacao()}, $primeiroNome',
                              style: Theme.of(context).textTheme.headlineMedium
                                  ?.copyWith(fontSize: 22),
                            ),
                          ],
                        ),
                      ),
                      IconButton(
                        tooltip: 'Sair',
                        onPressed: () => ref
                            .read(sessaoControllerProvider.notifier)
                            .logout(),
                        icon: const Icon(Icons.logout),
                      ),
                    ],
                  ),
                ),
              ),
              SliverPadding(
                padding: const EdgeInsets.all(20),
                sliver: resumoAsync.when(
                  loading: () => const SliverFillRemaining(
                    child: Center(child: CircularProgressIndicator()),
                  ),
                  error: (erro, _) => SliverFillRemaining(
                    child: Center(
                      child: Padding(
                        padding: const EdgeInsets.all(24),
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(
                              Icons.cloud_off_outlined,
                              size: 36,
                              color: VertexColors.textoTerciario,
                            ),
                            const SizedBox(height: 12),
                            const Text(
                              'Não foi possível carregar os dados agora.',
                              textAlign: TextAlign.center,
                            ),
                            const SizedBox(height: 14),
                            OutlinedButton(
                              onPressed: () => ref.invalidate(
                                dashboardProvider,
                              ),
                              child: const Text('Tentar de novo'),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  data: (resumo) => SliverGrid(
                    gridDelegate:
                        const SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: 2,
                          mainAxisSpacing: 12,
                          crossAxisSpacing: 12,
                          childAspectRatio: 1.35,
                        ),
                    delegate: SliverChildListDelegate([
                      KpiCard(
                        rotulo: 'Vendas hoje',
                        valor: formatarMoeda(resumo.vendasHoje),
                        icone: Icons.point_of_sale_outlined,
                        cor: VertexColors.primaria,
                      ),
                      KpiCard(
                        rotulo: 'Pedidos hoje',
                        valor: '${resumo.vendasHojeQtd}',
                        icone: Icons.receipt_long_outlined,
                        cor: VertexColors.primaria,
                      ),
                      KpiCard(
                        rotulo: 'Ticket médio',
                        valor: formatarMoeda(resumo.ticketMedio),
                        icone: Icons.trending_up,
                        cor: VertexColors.secundaria,
                      ),
                      KpiCard(
                        rotulo: 'Vendas do mês',
                        valor: formatarMoeda(resumo.vendasMes),
                        icone: Icons.calendar_month_outlined,
                        cor: VertexColors.secundaria,
                      ),
                      KpiCard(
                        rotulo: 'Saldo em caixa',
                        valor: formatarMoeda(resumo.saldoCaixa),
                        icone: Icons.account_balance_wallet_outlined,
                        cor: VertexColors.primaria,
                      ),
                      KpiCard(
                        rotulo: 'Contas a receber',
                        valor: formatarMoeda(resumo.contasReceber),
                        icone: Icons.call_received,
                        cor: VertexColors.alerta,
                      ),
                      KpiCard(
                        rotulo: 'Contas a pagar',
                        valor: formatarMoeda(resumo.contasPagar),
                        icone: Icons.call_made,
                        cor: VertexColors.erro,
                      ),
                      KpiCard(
                        rotulo: 'Produtos',
                        valor: '${resumo.produtos}',
                        icone: Icons.inventory_2_outlined,
                        cor: VertexColors.textoSecundario,
                        selo: resumo.estoqueBaixo > 0
                            ? '${resumo.estoqueBaixo} em alerta'
                            : null,
                      ),
                    ]),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
