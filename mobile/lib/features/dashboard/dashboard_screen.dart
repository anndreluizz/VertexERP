import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/cliente_analise.dart';
import '../../core/formatadores.dart';
import '../../core/providers.dart';
import '../../models/dashboard_resumo.dart';
import '../../models/venda.dart';
import '../../theme/animacoes.dart';
import '../../theme/componentes.dart';
import '../../theme/skeleton.dart';
import '../../theme/vertex_colors.dart';
import '../../theme/vertex_theme.dart';
import '../aprovacoes/aprovacoes_provider.dart';
import '../aprovacoes/aprovacoes_screen.dart';
import '../clientes/clientes_provider.dart';
import '../notificacoes/notificacoes_provider.dart';
import '../notificacoes/notificacoes_screen.dart';
import '../relatorios/relatorios_screen.dart';
import '../vendas/vendas_provider.dart';
import 'dashboard_provider.dart';

/// Recorte simples de "tempo real": sem WebSocket, so re-busca os
/// dados sozinho a cada X segundos enquanto a tela esta aberta -- o
/// suficiente pra um pagamento feito no Desktop aparecer no celular
/// sem precisar puxar pra atualizar.
const _intervaloAutoAtualizacao = Duration(seconds: 20);

const _textoSobreAzul = Color(0xFFC7D2E3);

const _abaVendas = 1;
const _abaClientes = 2;
const _abaFinanceiro = 3;

class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({super.key});

  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

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

  Future<void> _atualizar() async {
    ref.invalidate(vendasProvider);
    ref.invalidate(movimentosFiadoProvider);
    ref.invalidate(aprovacoesPendentesProvider);
    await ref.refresh(dashboardProvider.future).then((_) {});
  }

  void _irPara(int aba, {FiltroClientes? filtro}) {
    if (filtro != null) {
      ref.read(filtroClientesProvider.notifier).state = filtro;
    }
    ref.read(abaSelecionadaProvider.notifier).state = aba;
  }

  void _abrir(Widget tela) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => tela));
  }

  @override
  Widget build(BuildContext context) {
    final resumoAsync = ref.watch(dashboardProvider);

    return Scaffold(
      body: RefreshIndicator(
        onRefresh: _atualizar,
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            _Topo(
              deCache: resumoAsync.valueOrNull?.deCache == true,
              atualizadoEm: resumoAsync.valueOrNull?.atualizadoEm,
              aoAbrirNotificacoes: () => _abrir(const NotificacoesScreen()),
            ),
            Transform.translate(
              offset: const Offset(0, -76),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: resumoAsync.when(
                  loading: () =>
                      const SkeletonBox(height: 220, borderRadius: 20),
                  error: (erro, _) => _ErroCarregar(
                    aoTentar: () => ref.invalidate(dashboardProvider),
                  ),
                  data: (carregado) =>
                      _CartaoVendasHoje(resumo: carregado.resumo),
                ),
              ),
            ),
            Transform.translate(
              offset: const Offset(0, -58),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: entradaEscalonada([
                  _AtalhosRapidos(
                    aoReceber: () => _irPara(_abaClientes),
                    aoCobrar: () => _irPara(
                      _abaClientes,
                      filtro: FiltroClientes.inadimplentes,
                    ),
                    aoPagar: () => _irPara(_abaFinanceiro),
                    aoRelatorio: () => _abrir(const RelatoriosScreen()),
                  ),
                  if (resumoAsync.valueOrNull?.resumo case final resumo?)
                    _Atencao(
                      resumo: resumo,
                      aoInadimplentes: () => _irPara(
                        _abaClientes,
                        filtro: FiltroClientes.inadimplentes,
                      ),
                      aoContas: () => _irPara(_abaFinanceiro),
                      aoAprovacoes: () => _abrir(const AprovacoesScreen()),
                    ),
                  _FiadoDaLoja(
                    recebidoHoje:
                        resumoAsync.valueOrNull?.resumo.fiadoRecebidoHoje,
                    aoTocar: () => _irPara(_abaClientes),
                  ),
                ]),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

String _saudacao() {
  final hora = DateTime.now().hour;
  if (hora < 12) return 'Bom dia';
  if (hora < 18) return 'Boa tarde';
  return 'Boa noite';
}

const _diasSemana = [
  'Segunda',
  'Terça',
  'Quarta',
  'Quinta',
  'Sexta',
  'Sábado',
  'Domingo',
];
const _meses = [
  'janeiro',
  'fevereiro',
  'março',
  'abril',
  'maio',
  'junho',
  'julho',
  'agosto',
  'setembro',
  'outubro',
  'novembro',
  'dezembro',
];

class _Topo extends ConsumerWidget {
  const _Topo({
    required this.deCache,
    required this.atualizadoEm,
    required this.aoAbrirNotificacoes,
  });

  final bool deCache;
  final DateTime? atualizadoEm;
  final VoidCallback aoAbrirNotificacoes;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sessao = ref.watch(sessaoControllerProvider);
    final naoLidas = ref.watch(naoLidasProvider);
    final primeiroNome = sessao.usuario?.nome.split(' ').first ?? '';
    final hoje = DateTime.now();
    final data =
        '${_diasSemana[hoje.weekday - 1]}, ${hoje.day} de ${_meses[hoje.month - 1]}';

    final status = deCache && atualizadoEm != null
        ? 'Sem conexão · dados de ${formatarDataHora(atualizadoEm!)}'
        : '${sessao.nomeLoja ?? 'Loja'} conectada';

    return Container(
      color: VertexColors.escuro ? VertexColors.card : VertexColors.sidebar,
      padding: EdgeInsets.fromLTRB(
        20,
        MediaQuery.of(context).padding.top + 18,
        16,
        96,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 40,
                height: 40,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: VertexPaleta.claro.primaria,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Text(
                  'V',
                  style: TextStyle(
                    fontFamily: VertexTheme.fonteDisplay,
                    fontWeight: FontWeight.w700,
                    fontSize: 18,
                    color: Colors.white,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      data,
                      style: const TextStyle(
                        fontSize: 13,
                        color: _textoSobreAzul,
                      ),
                    ),
                    Text(
                      primeiroNome.isEmpty
                          ? _saudacao()
                          : '${_saudacao()}, $primeiroNome',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontFamily: VertexTheme.fonteDisplay,
                        fontWeight: FontWeight.w700,
                        fontSize: 20,
                        color: Colors.white,
                      ),
                    ),
                  ],
                ),
              ),
              Material(
                color: const Color(0xFF1C3357),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                  side: const BorderSide(color: Color(0xFF24406B)),
                ),
                child: InkWell(
                  borderRadius: BorderRadius.circular(12),
                  onTap: aoAbrirNotificacoes,
                  child: SizedBox(
                    width: 44,
                    height: 44,
                    child: Badge(
                      isLabelVisible: naoLidas > 0,
                      label: Text(naoLidas > 99 ? '99+' : '$naoLidas'),
                      offset: const Offset(-4, 4),
                      child: const Center(
                        child: Icon(
                          Icons.notifications_none_rounded,
                          color: Colors.white,
                          size: 22,
                          semanticLabel: 'Notificações',
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: deCache
                      ? const Color(0xFFD69A3E)
                      : const Color(0xFF3FBFA0),
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  status,
                  style: const TextStyle(
                    fontSize: 12.5,
                    color: _textoSobreAzul,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ErroCarregar extends StatelessWidget {
  const _ErroCarregar({required this.aoTentar});

  final VoidCallback aoTentar;

  @override
  Widget build(BuildContext context) {
    return _Cartao(
      child: Column(
        children: [
          Icon(
            Icons.cloud_off_outlined,
            size: 32,
            color: VertexColors.textoTerciario,
          ),
          const SizedBox(height: 10),
          const Text(
            'Não foi possível carregar os dados agora.',
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 12),
          OutlinedButton(
            onPressed: aoTentar,
            child: const Text('Tentar de novo'),
          ),
        ],
      ),
    );
  }
}

class _Cartao extends StatelessWidget {
  const _Cartao({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: VertexColors.card,
        borderRadius: BorderRadius.circular(20),
        border: VertexColors.escuro
            ? Border.all(color: VertexColors.borda)
            : null,
        boxShadow: VertexColors.escuro
            ? null
            : const [
                BoxShadow(
                  color: Color(0x0F16213B),
                  blurRadius: 2,
                  offset: Offset(0, 1),
                ),
                BoxShadow(
                  color: Color(0x1416213B),
                  blurRadius: 24,
                  offset: Offset(0, 6),
                ),
              ],
      ),
      child: child,
    );
  }
}

/// Total vendido por dia nos ultimos 7 dias (hoje por ultimo).
List<double> _ultimos7Dias(List<Venda> vendas) {
  final agora = DateTime.now();
  final hoje = DateTime(agora.year, agora.month, agora.day);
  final totais = List<double>.filled(7, 0);
  for (final v in vendas) {
    if (v.status == 'CANCELADA') continue;
    final dia = DateTime(v.data.year, v.data.month, v.data.day);
    final atras = hoje.difference(dia).inDays;
    if (atras >= 0 && atras < 7) totais[6 - atras] += v.valorTotal;
  }
  return totais;
}

class _CartaoVendasHoje extends ConsumerWidget {
  const _CartaoVendasHoje({required this.resumo});

  final DashboardResumo resumo;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final vendas = ref.watch(vendasProvider).valueOrNull;
    final dias = vendas == null ? null : _ultimos7Dias(vendas);
    final ontem = dias?[5];

    String? variacao;
    var subiu = true;
    if (ontem != null && ontem > 0) {
      final pct = ((resumo.vendasHoje - ontem) / ontem * 100).round();
      subiu = pct >= 0;
      variacao = '${subiu ? '+' : ''}$pct% vs ontem';
    }

    return Semantics(
      button: true,
      child: GestureDetector(
        onTap: () =>
            ref.read(abaSelecionadaProvider.notifier).state = _abaVendas,
        child: _Cartao(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'VENDIDO HOJE',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            letterSpacing: 0.6,
                            color: VertexColors.textoSecundario,
                          ),
                        ),
                        const SizedBox(height: 4),
                        FittedBox(
                          fit: BoxFit.scaleDown,
                          alignment: Alignment.centerLeft,
                          child: Text(
                            formatarMoeda(resumo.vendasHoje),
                            style: TextStyle(
                              fontFamily: VertexTheme.fonteDisplay,
                              fontSize: 34,
                              fontWeight: FontWeight.w700,
                              height: 1.1,
                              color: VertexColors.texto,
                              fontFeatures: tabular,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (variacao != null)
                    Selo(
                      variacao,
                      fundo: subiu
                          ? VertexColors.sucessoClaro
                          : VertexColors.erroClaro,
                      cor: subiu ? VertexColors.sucesso : VertexColors.erro,
                    ),
                ],
              ),
              const SizedBox(height: 14),
              _BarrasSemana(dias: dias),
              const SizedBox(height: 12),
              Divider(color: VertexColors.borda, height: 1),
              const SizedBox(height: 12),
              Row(
                children: [
                  _Numero(rotulo: 'Vendas', valor: '${resumo.vendasHojeQtd}'),
                  _Numero(
                    rotulo: 'Ticket médio',
                    valor: formatarMoeda(resumo.ticketMedio),
                  ),
                  _Numero(
                    rotulo: 'No mês',
                    valor: formatarMoeda(resumo.vendasMes),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _BarrasSemana extends StatelessWidget {
  const _BarrasSemana({required this.dias});

  final List<double>? dias;

  @override
  Widget build(BuildContext context) {
    const rotulos = ['D', 'S', 'T', 'Q', 'Q', 'S', 'S'];
    final hoje = DateTime.now();
    final valores = dias ?? List<double>.filled(7, 0);
    final maior = valores.fold<double>(0, (m, v) => v > m ? v : m);

    return Semantics(
      label: 'Vendas dos últimos 7 dias',
      child: SizedBox(
        height: 72,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            for (var i = 0; i < 7; i++) ...[
              if (i > 0) const SizedBox(width: 6),
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    Expanded(
                      child: Align(
                        alignment: Alignment.bottomCenter,
                        child: FractionallySizedBox(
                          heightFactor: maior <= 0
                              ? 0.06
                              : (valores[i] / maior).clamp(0.06, 1.0),
                          child: Container(
                            decoration: BoxDecoration(
                              color: i == 6
                                  ? VertexColors.primaria
                                  : VertexColors.primariaClara,
                              borderRadius: BorderRadius.circular(5),
                            ),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      // rotulo do dia da semana de cada barra (hoje = ultima)
                      rotulos[hoje.subtract(Duration(days: 6 - i)).weekday % 7],
                      style: TextStyle(
                        fontSize: 10.5,
                        fontWeight: i == 6 ? FontWeight.w700 : FontWeight.w500,
                        color: i == 6
                            ? VertexColors.texto
                            : VertexColors.textoSecundario,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _Numero extends StatelessWidget {
  const _Numero({required this.rotulo, required this.valor});

  final String rotulo;
  final String valor;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            rotulo,
            style: TextStyle(fontSize: 12, color: VertexColors.textoSecundario),
          ),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(
              valor,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                fontFeatures: tabular,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _AtalhosRapidos extends StatelessWidget {
  const _AtalhosRapidos({
    required this.aoReceber,
    required this.aoCobrar,
    required this.aoPagar,
    required this.aoRelatorio,
  });

  final VoidCallback aoReceber;
  final VoidCallback aoCobrar;
  final VoidCallback aoPagar;
  final VoidCallback aoRelatorio;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 18, 16, 0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _Atalho(
            icone: Icons.payments_outlined,
            rotulo: 'Receber fiado',
            fundo: VertexColors.sucessoClaro,
            cor: VertexColors.escuro
                ? VertexColors.sucesso
                : VertexColors.secundaria,
            aoTocar: aoReceber,
          ),
          _Atalho(
            icone: Icons.chat_outlined,
            rotulo: 'Cobrar',
            fundo: VertexColors.primariaClara,
            cor: VertexColors.escuro
                ? VertexColors.texto
                : VertexColors.primaria,
            aoTocar: aoCobrar,
          ),
          _Atalho(
            icone: Icons.receipt_long_outlined,
            rotulo: 'Pagar conta',
            fundo: VertexColors.alertaClaro,
            cor: VertexColors.alertaTexto,
            aoTocar: aoPagar,
          ),
          _Atalho(
            icone: Icons.bar_chart_rounded,
            rotulo: 'Relatório',
            fundo: VertexColors.card,
            cor: VertexColors.texto,
            borda: true,
            aoTocar: aoRelatorio,
          ),
        ],
      ),
    );
  }
}

class _Atalho extends StatelessWidget {
  const _Atalho({
    required this.icone,
    required this.rotulo,
    required this.fundo,
    required this.cor,
    required this.aoTocar,
    this.borda = false,
  });

  final IconData icone;
  final String rotulo;
  final Color fundo;
  final Color cor;
  final VoidCallback aoTocar;
  final bool borda;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: aoTocar,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Column(
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: fundo,
                  borderRadius: BorderRadius.circular(18),
                  border: borda ? Border.all(color: VertexColors.borda) : null,
                ),
                child: Icon(icone, color: cor, size: 24),
              ),
              const SizedBox(height: 6),
              Text(
                rotulo,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ItemAtencao {
  const _ItemAtencao({
    required this.icone,
    required this.fundo,
    required this.cor,
    required this.titulo,
    required this.detalhe,
    required this.aoTocar,
  });

  final IconData icone;
  final Color fundo;
  final Color cor;
  final String titulo;
  final String detalhe;
  final VoidCallback aoTocar;
}

class _Atencao extends ConsumerWidget {
  const _Atencao({
    required this.resumo,
    required this.aoInadimplentes,
    required this.aoContas,
    required this.aoAprovacoes,
  });

  final DashboardResumo resumo;
  final VoidCallback aoInadimplentes;
  final VoidCallback aoContas;
  final VoidCallback aoAprovacoes;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final analises = ref.watch(analisesClientesProvider).valueOrNull;
    // operador sem permissao de aprovar recebe erro aqui: so nao mostra
    final aprovacoes = ref.watch(aprovacoesPendentesProvider).valueOrNull;

    final inadimplentes = analises?.values.where((a) => a.inadimplente) ?? [];
    final valorInadimplente = inadimplentes.fold<double>(
      0,
      (s, a) => s + a.saldoDevedor,
    );

    final itens = <_ItemAtencao>[
      if (inadimplentes.isNotEmpty)
        _ItemAtencao(
          icone: Icons.schedule_rounded,
          fundo: VertexColors.erroClaro,
          cor: VertexColors.erro,
          titulo:
              '${inadimplentes.length} ${inadimplentes.length == 1 ? 'cliente inadimplente' : 'clientes inadimplentes'}',
          detalhe:
              'Mais de $prazoInadimplenciaDias dias sem pagar · '
              '${formatarMoeda(valorInadimplente)}',
          aoTocar: aoInadimplentes,
        ),
      if (resumo.contasVencidasQtd > 0)
        _ItemAtencao(
          icone: Icons.event_busy_outlined,
          fundo: VertexColors.erroClaro,
          cor: VertexColors.erro,
          titulo:
              '${resumo.contasVencidasQtd} ${resumo.contasVencidasQtd == 1 ? 'conta vencida' : 'contas vencidas'}',
          detalhe: '${formatarMoeda(resumo.contasVencidasValor)} em atraso',
          aoTocar: aoContas,
        ),
      if (resumo.contasVencendoHojeQtd > 0)
        _ItemAtencao(
          icone: Icons.event_outlined,
          fundo: VertexColors.alertaClaro,
          cor: VertexColors.alertaTexto,
          titulo:
              '${resumo.contasVencendoHojeQtd} ${resumo.contasVencendoHojeQtd == 1 ? 'conta vence hoje' : 'contas vencem hoje'}',
          detalhe: formatarMoeda(resumo.contasVencendoHojeValor),
          aoTocar: aoContas,
        ),
      if (aprovacoes != null && aprovacoes.isNotEmpty)
        _ItemAtencao(
          icone: Icons.verified_user_outlined,
          fundo: VertexColors.primariaClara,
          cor: VertexColors.escuro ? VertexColors.texto : VertexColors.primaria,
          titulo:
              '${aprovacoes.length} ${aprovacoes.length == 1 ? 'pedido para aprovar' : 'pedidos para aprovar'}',
          detalhe: aprovacoes.first.descricao,
          aoTocar: aoAprovacoes,
        ),
      if (resumo.estoqueBaixo > 0)
        _ItemAtencao(
          icone: Icons.inventory_2_outlined,
          fundo: VertexColors.alertaClaro,
          cor: VertexColors.alertaTexto,
          titulo:
              '${resumo.estoqueBaixo} ${resumo.estoqueBaixo == 1 ? 'produto com estoque baixo' : 'produtos com estoque baixo'}',
          detalhe: 'Veja em Mais › Estoque',
          aoTocar: () => ref.read(abaSelecionadaProvider.notifier).state = 4,
        ),
    ];

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 24, 16, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TituloSecao(
            'Precisa da sua atenção',
            resumo: itens.isEmpty
                ? null
                : '${itens.length} ${itens.length == 1 ? 'item' : 'itens'}',
          ),
          if (itens.isEmpty)
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: VertexColors.sucessoClaro,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Row(
                children: [
                  Icon(Icons.check_circle_outline, color: VertexColors.sucesso),
                  const SizedBox(width: 10),
                  const Expanded(
                    child: Text('Tudo em dia por aqui. Nada pendente agora.'),
                  ),
                ],
              ),
            )
          else
            Card(
              clipBehavior: Clip.antiAlias,
              child: Column(
                children: [
                  for (var i = 0; i < itens.length; i++) ...[
                    if (i > 0) const Divider(indent: 66),
                    _LinhaAtencao(item: itens[i]),
                  ],
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _LinhaAtencao extends StatelessWidget {
  const _LinhaAtencao({required this.item});

  final _ItemAtencao item;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: item.aoTocar,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: item.fundo,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(item.icone, color: item.cor, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.titulo,
                    style: const TextStyle(
                      fontSize: 14.5,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  Text(
                    item.detalhe,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 13,
                      color: VertexColors.textoSecundario,
                    ),
                  ),
                ],
              ),
            ),
            Icon(
              Icons.chevron_right_rounded,
              color: VertexColors.textoSecundario,
            ),
          ],
        ),
      ),
    );
  }
}

class _FiadoDaLoja extends ConsumerWidget {
  const _FiadoDaLoja({required this.recebidoHoje, required this.aoTocar});

  final double? recebidoHoje;
  final VoidCallback aoTocar;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final analisesAsync = ref.watch(analisesClientesProvider);
    final movimentos = ref.watch(movimentosFiadoProvider).valueOrNull;

    final agora = DateTime.now();
    final recebidoMes = movimentos
        ?.where(
          (m) =>
              m.tipo == 'PAGAMENTO' &&
              m.data.year == agora.year &&
              m.data.month == agora.month,
        )
        .fold<double>(0, (s, m) => s + m.valor);

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 24, 16, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const TituloSecao('Fiado da loja'),
          analisesAsync.when(
            loading: () => const SkeletonBox(height: 120, borderRadius: 16),
            error: (erro, _) => const SizedBox.shrink(),
            data: (analises) {
              final devendo = analises.values.where((a) => a.devendo).toList();
              final total = devendo.fold<double>(
                0,
                (s, a) => s + a.saldoDevedor,
              );
              final inad = devendo.where((a) => a.inadimplente).length;
              final atraso = devendo
                  .where((a) => a.status == StatusCliente.pagaComAtraso)
                  .length;
              final emDia = devendo.length - inad - atraso;

              final partes = [
                (emDia, VertexColors.sucesso, 'Em dia'),
                (atraso, VertexColors.alerta, 'Pagam com atraso'),
                (inad, VertexColors.erro, 'Inadimplentes'),
              ];

              return Card(
                clipBehavior: Clip.antiAlias,
                child: InkWell(
                  onTap: aoTocar,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Em aberto · ${devendo.length} clientes',
                                    style: TextStyle(
                                      fontSize: 13,
                                      color: VertexColors.textoSecundario,
                                    ),
                                  ),
                                  FittedBox(
                                    fit: BoxFit.scaleDown,
                                    alignment: Alignment.centerLeft,
                                    child: Text(
                                      formatarMoeda(total),
                                      style: TextStyle(
                                        fontFamily: VertexTheme.fonteDisplay,
                                        fontSize: 24,
                                        fontWeight: FontWeight.w700,
                                        color: VertexColors.texto,
                                        fontFeatures: tabular,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            if (recebidoMes != null)
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  Text(
                                    'Recebido no mês',
                                    style: TextStyle(
                                      fontSize: 13,
                                      color: VertexColors.textoSecundario,
                                    ),
                                  ),
                                  Text(
                                    formatarMoeda(recebidoMes),
                                    style: TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.w700,
                                      color: VertexColors.sucesso,
                                      fontFeatures: tabular,
                                    ),
                                  ),
                                ],
                              ),
                          ],
                        ),
                        if (devendo.isNotEmpty) ...[
                          const SizedBox(height: 12),
                          ClipRRect(
                            borderRadius: BorderRadius.circular(6),
                            child: SizedBox(
                              height: 10,
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.stretch,
                                children: [
                                  for (final (qtd, cor, _) in partes)
                                    if (qtd > 0)
                                      Expanded(
                                        flex: qtd,
                                        child: Padding(
                                          padding: const EdgeInsets.only(
                                            right: 2,
                                          ),
                                          child: ColoredBox(color: cor),
                                        ),
                                      ),
                                ],
                              ),
                            ),
                          ),
                          const SizedBox(height: 10),
                          Wrap(
                            spacing: 14,
                            runSpacing: 6,
                            children: [
                              for (final (qtd, cor, rotulo) in partes)
                                Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Container(
                                      width: 8,
                                      height: 8,
                                      decoration: BoxDecoration(
                                        color: cor,
                                        borderRadius: BorderRadius.circular(2),
                                      ),
                                    ),
                                    const SizedBox(width: 6),
                                    Text(
                                      '$rotulo · $qtd',
                                      style: TextStyle(
                                        fontSize: 12.5,
                                        color: VertexColors.textoSecundario,
                                      ),
                                    ),
                                  ],
                                ),
                            ],
                          ),
                        ],
                        if (recebidoHoje != null && recebidoHoje! > 0) ...[
                          const SizedBox(height: 10),
                          Text(
                            'Hoje entraram ${formatarMoeda(recebidoHoje!)} de fiado.',
                            style: TextStyle(
                              fontSize: 12.5,
                              color: VertexColors.textoSecundario,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
          const SizedBox(height: 8),
        ],
      ),
    );
  }
}
