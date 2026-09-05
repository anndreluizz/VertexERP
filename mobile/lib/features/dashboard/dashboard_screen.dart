import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../core/providers.dart';
import '../../theme/animacoes.dart';
import '../../theme/skeleton.dart';
import '../../theme/vertex_colors.dart';
import 'dashboard_provider.dart';
import 'widgets/aviso_vencimento_banner.dart';
import 'widgets/grafico_pago_pendente.dart';
import 'widgets/grafico_serie_mensal.dart';
import 'widgets/kpi_card.dart';

class _AvisoOffline extends StatelessWidget {
  const _AvisoOffline({required this.atualizadoEm});

  final DateTime atualizadoEm;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.fromLTRB(20, 0, 20, 4),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: VertexColors.alertaClaro,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.cloud_off_outlined,
            size: 16,
            color: VertexColors.alerta,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Sem conexão — mostrando dados de '
              '${formatarDataHora(atualizadoEm)}',
              style: const TextStyle(fontSize: 12, color: VertexColors.alerta),
            ),
          ),
        ],
      ),
    );
  }
}

/// Cabecalho de secao acima dos graficos -- so pra separar visualmente
/// os KPIs (o "agora") da analise mensal (a "tendencia").
class _TituloSecao extends StatelessWidget {
  const _TituloSecao(this.texto);

  final String texto;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 4, 4, 10),
      child: Text(
        texto,
        style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
      ),
    );
  }
}

/// Contadores operacionais (produtos/clientes/fornecedores) -- ficam
/// discretos embaixo dos KPIs financeiros, sem competir com eles.
class _FaixaOperacional extends StatelessWidget {
  const _FaixaOperacional({
    required this.produtos,
    required this.estoqueBaixo,
    required this.clientes,
    required this.fornecedores,
  });

  final int produtos;
  final int estoqueBaixo;
  final int clientes;
  final int fornecedores;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: VertexColors.card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: VertexColors.borda),
      ),
      child: Row(
        children: [
          Expanded(
            child: _ItemOperacional(
              icone: Icons.inventory_2_outlined,
              rotulo: 'Produtos',
              valor: '$produtos',
              selo: estoqueBaixo > 0 ? '$estoqueBaixo em alerta' : null,
            ),
          ),
          Container(width: 1, height: 30, color: VertexColors.borda),
          Expanded(
            child: _ItemOperacional(
              icone: Icons.people_outline,
              rotulo: 'Clientes',
              valor: '$clientes',
            ),
          ),
          Container(width: 1, height: 30, color: VertexColors.borda),
          Expanded(
            child: _ItemOperacional(
              icone: Icons.local_shipping_outlined,
              rotulo: 'Fornecedores',
              valor: '$fornecedores',
            ),
          ),
        ],
      ),
    );
  }
}

class _ItemOperacional extends StatelessWidget {
  const _ItemOperacional({
    required this.icone,
    required this.rotulo,
    required this.valor,
    this.selo,
  });

  final IconData icone;
  final String rotulo;
  final String valor;
  final String? selo;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Icon(icone, size: 16, color: VertexColors.textoSecundario),
        const SizedBox(height: 4),
        Text(
          valor,
          style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
        ),
        Text(
          rotulo,
          style: TextStyle(fontSize: 10.5, color: VertexColors.textoSecundario),
        ),
        if (selo != null)
          Text(
            selo!,
            style: const TextStyle(
              fontSize: 9.5,
              fontWeight: FontWeight.w700,
              color: VertexColors.erro,
            ),
          ),
      ],
    );
  }
}

class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({super.key});

  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

/// Recorte simples de "tempo real": sem WebSocket, so re-busca os
/// dados sozinho a cada X segundos enquanto a tela esta aberta -- o
/// suficiente pra um pagamento feito no Desktop aparecer no celular
/// sem precisar puxar pra atualizar.
const _intervaloAutoAtualizacao = Duration(seconds: 20);

class _DashboardScreenState extends ConsumerState<DashboardScreen> {
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(_intervaloAutoAtualizacao, (_) {
      ref.invalidate(dashboardProvider);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  String _saudacao() {
    final hora = DateTime.now().hour;
    if (hora < 12) return 'Bom dia';
    if (hora < 18) return 'Boa tarde';
    return 'Boa noite';
  }

  Future<void> _confirmarLogout(BuildContext context) async {
    final confirmar = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Sair da conta?'),
        content: const Text(
          'Você vai precisar fazer login de novo pra acessar a conta '
          'neste aparelho.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancelar'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Sair'),
          ),
        ],
      ),
    );

    if (confirmar != true || !context.mounted) return;

    ref.read(sessaoControllerProvider.notifier).logout();
  }

  @override
  Widget build(BuildContext context) {
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
                                  style: Theme.of(
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
                        onPressed: () => _confirmarLogout(context),
                        icon: const Icon(Icons.logout),
                      ),
                    ],
                  ),
                ),
              ),
              if (resumoAsync.valueOrNull?.deCache == true)
                SliverToBoxAdapter(
                  child: _AvisoOffline(
                    atualizadoEm: resumoAsync.value!.atualizadoEm,
                  ),
                ),
              resumoAsync.when(
                loading: () => const SliverPadding(
                  padding: EdgeInsets.all(20),
                  sliver: SliverToBoxAdapter(child: SkeletonKpiGrid()),
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
                            onPressed: () => ref.invalidate(dashboardProvider),
                            child: const Text('Tentar de novo'),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                data: (carregado) {
                  final resumo = carregado.resumo;

                  return SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
                    sliver: SliverList(
                      delegate: SliverChildListDelegate([
                        if (resumo.totalAvisoVencimento > 0)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 6),
                            child: AvisoVencimentoBanner(
                              vencidasQtd: resumo.contasVencidasQtd,
                              vencidasValor: resumo.contasVencidasValor,
                              vencendoHojeQtd: resumo.contasVencendoHojeQtd,
                              vencendoHojeValor: resumo.contasVencendoHojeValor,
                              aoTocar: () => ref
                                  .read(abaSelecionadaProvider.notifier)
                                  .state = 3,
                            ),
                          ),
                        GridView.count(
                          crossAxisCount: 2,
                          mainAxisSpacing: 12,
                          crossAxisSpacing: 12,
                          childAspectRatio: 1.15,
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          children: entradaEscalonada([
                            KpiCard(
                              rotulo: 'Vendas hoje',
                              valor: formatarMoeda(resumo.vendasHoje),
                              icone: Icons.point_of_sale_outlined,
                              cor: VertexColors.primaria,
                              selo: resumo.vendasHojeQtd > 0
                                  ? '${resumo.vendasHojeQtd} pedidos'
                                  : null,
                            ),
                            KpiCard(
                              rotulo: 'Ticket médio',
                              valor: formatarMoeda(resumo.ticketMedio),
                              icone: Icons.trending_up,
                              cor: VertexColors.primaria,
                            ),
                            KpiCard(
                              rotulo: 'Vendas do mês',
                              valor: formatarMoeda(resumo.vendasMes),
                              icone: Icons.calendar_month_outlined,
                              cor: VertexColors.primaria,
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
                              cor: VertexColors.secundaria,
                            ),
                            KpiCard(
                              rotulo: 'Contas a pagar',
                              valor: formatarMoeda(resumo.contasPagar),
                              icone: Icons.call_made,
                              cor: VertexColors.textoSecundario,
                            ),
                            KpiCard(
                              rotulo: 'Contas vencidas',
                              valor: formatarMoeda(resumo.contasVencidasValor),
                              icone: Icons.error_outline,
                              cor: VertexColors.erro,
                              selo: resumo.contasVencidasQtd > 0
                                  ? '${resumo.contasVencidasQtd}'
                                  : null,
                            ),
                            KpiCard(
                              rotulo: 'Vencendo hoje',
                              valor: formatarMoeda(
                                resumo.contasVencendoHojeValor,
                              ),
                              icone: Icons.today_outlined,
                              cor: VertexColors.alerta,
                              selo: resumo.contasVencendoHojeQtd > 0
                                  ? '${resumo.contasVencendoHojeQtd}'
                                  : null,
                            ),
                            KpiCard(
                              rotulo: 'Pago hoje',
                              valor: formatarMoeda(
                                resumo.contasPagasHojeValor,
                              ),
                              icone: Icons.check_circle_outline,
                              cor: VertexColors.secundaria,
                              selo: resumo.contasPagasHojeQtd > 0
                                  ? '${resumo.contasPagasHojeQtd}'
                                  : null,
                            ),
                            KpiCard(
                              rotulo: 'Recebido hoje',
                              valor: formatarMoeda(resumo.fiadoRecebidoHoje),
                              icone: Icons.savings_outlined,
                              cor: VertexColors.secundaria,
                            ),
                          ]),
                        ),
                        const SizedBox(height: 14),
                        _FaixaOperacional(
                          produtos: resumo.produtos,
                          estoqueBaixo: resumo.estoqueBaixo,
                          clientes: resumo.clientes,
                          fornecedores: resumo.fornecedores,
                        ),
                        const SizedBox(height: 24),
                        const _TituloSecao('Análise financeira'),
                        GraficoPagoPendente(
                          pago: resumo.contasMesPago,
                          pendente: resumo.contasMesPendente,
                        ),
                        const SizedBox(height: 12),
                        GraficoSerieMensal(
                          titulo: 'Recebimentos',
                          subtitulo: 'Últimos 6 meses',
                          pontos: resumo.serieRecebimentosMensal,
                          cor: VertexColors.secundaria,
                        ),
                        const SizedBox(height: 12),
                        GraficoSerieMensal(
                          titulo: 'Pagamentos',
                          subtitulo: 'Últimos 6 meses',
                          pontos: resumo.seriePagamentosMensal,
                          cor: VertexColors.erro,
                        ),
                      ]),
                    ),
                  );
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}
