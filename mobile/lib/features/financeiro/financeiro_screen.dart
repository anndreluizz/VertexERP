import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../models/conta_pagar.dart';
import '../../theme/componentes.dart';
import '../../theme/lista_agrupada.dart';
import '../../theme/skeleton.dart';
import '../../theme/vertex_colors.dart';
import '../../theme/vertex_theme.dart';
import 'comprovante_screen.dart';
import 'financeiro_provider.dart';
import 'historico_conta_screen.dart';
import 'realizar_pagamento_screen.dart';
import 'status_conta.dart';

/// Mesmo recorte simples de "tempo real" do Dashboard (ver
/// dashboard_screen.dart) -- sem WebSocket, so re-busca sozinho.
const _intervaloAutoAtualizacao = Duration(seconds: 20);

class FinanceiroScreen extends ConsumerStatefulWidget {
  const FinanceiroScreen({super.key});

  @override
  ConsumerState<FinanceiroScreen> createState() => _FinanceiroScreenState();
}

class _FinanceiroScreenState extends ConsumerState<FinanceiroScreen> {
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(_intervaloAutoAtualizacao, (_) {
      ref.invalidate(contasPagarProvider);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Contas a pagar')),
      body: const _AbaContasPagar(),
    );
  }
}

/// Vencido ou vencendo em ate 1 dia esquenta a cor — mesmo criterio
/// usado na tela de Contas a Pagar do Desktop.
/// Filtros rapidos da aba "A Pagar" -- cada um e um recorte simples
/// por cima da mesma lista ja carregada, sem ida nova ao servidor.
enum FiltroRapidoContaPagar {
  todas,
  estaSemana,
  aVencer,
  venceHoje,
  vencidas,
  pagas,
  esteMes,
  semBoleto,
}

extension _FiltroRapidoInfo on FiltroRapidoContaPagar {
  String get rotulo => switch (this) {
    FiltroRapidoContaPagar.todas => 'Todas',
    FiltroRapidoContaPagar.estaSemana => 'Esta semana',
    FiltroRapidoContaPagar.aVencer => 'A vencer',
    FiltroRapidoContaPagar.venceHoje => 'Vence hoje',
    FiltroRapidoContaPagar.vencidas => 'Vencidas',
    FiltroRapidoContaPagar.pagas => 'Pagas',
    FiltroRapidoContaPagar.esteMes => 'Este mês',
    FiltroRapidoContaPagar.semBoleto => 'Sem boleto',
  };

  bool aplica(ContaPagar conta) {
    final hoje = DateTime.now();

    return switch (this) {
      FiltroRapidoContaPagar.todas => true,
      FiltroRapidoContaPagar.estaSemana => _venceNaSemana(conta),
      FiltroRapidoContaPagar.aVencer =>
        statusVisual(conta) == StatusVisualConta.aVencer,
      FiltroRapidoContaPagar.venceHoje =>
        statusVisual(conta) == StatusVisualConta.venceHoje,
      FiltroRapidoContaPagar.vencidas =>
        statusVisual(conta) == StatusVisualConta.vencida,
      FiltroRapidoContaPagar.pagas =>
        statusVisual(conta) == StatusVisualConta.paga,
      FiltroRapidoContaPagar.esteMes =>
        conta.dataVencimento.year == hoje.year &&
            conta.dataVencimento.month == hoje.month,
      FiltroRapidoContaPagar.semBoleto => !conta.temDocumento,
    };
  }
}

/// pendente vencendo de hoje ate daqui a 7 dias
bool _venceNaSemana(ContaPagar conta) {
  final status = statusVisual(conta);
  if (status != StatusVisualConta.venceHoje &&
      status != StatusVisualConta.aVencer) {
    return false;
  }
  final hoje = DateTime.now();
  final dias = DateTime(
    conta.dataVencimento.year,
    conta.dataVencimento.month,
    conta.dataVencimento.day,
  ).difference(DateTime(hoje.year, hoje.month, hoje.day)).inDays;
  return dias <= 7;
}

bool _combinaComBusca(ContaPagar conta, String termo) {
  if (termo.isEmpty) return true;

  final alvo = termo.toLowerCase();

  return (conta.descricao ?? '').toLowerCase().contains(alvo) ||
      (conta.categoria ?? '').toLowerCase().contains(alvo) ||
      (conta.numeroBoleto ?? '').toLowerCase().contains(alvo) ||
      statusVisual(conta).rotulo.toLowerCase().contains(alvo) ||
      conta.valor.toStringAsFixed(2).contains(alvo);
}

class _AbaContasPagar extends ConsumerStatefulWidget {
  const _AbaContasPagar();

  @override
  ConsumerState<_AbaContasPagar> createState() => _AbaContasPagarState();
}

class _AbaContasPagarState extends ConsumerState<_AbaContasPagar> {
  FiltroRapidoContaPagar _filtro = FiltroRapidoContaPagar.todas;
  final _buscaController = TextEditingController();
  String _busca = '';

  @override
  void dispose() {
    _buscaController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final contasAsync = ref.watch(contasPagarProvider);

    final todas = contasAsync.valueOrNull;

    return Column(
      children: [
        if (todas != null)
          _QuadrosResumo(
            contas: todas,
            filtro: _filtro,
            aoEscolher: (f) => setState(
              () => _filtro = _filtro == f ? FiltroRapidoContaPagar.todas : f,
            ),
          ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
          child: TextField(
            controller: _buscaController,
            onChanged: (valor) => setState(() => _busca = valor),
            decoration: InputDecoration(
              hintText: 'Buscar por descrição, categoria, boleto...',
              prefixIcon: const Icon(Icons.search_rounded, size: 20),
              suffixIcon: _busca.isEmpty
                  ? null
                  : IconButton(
                      icon: const Icon(Icons.close, size: 18),
                      onPressed: () => setState(() {
                        _buscaController.clear();
                        _busca = '';
                      }),
                    ),
            ),
          ),
        ),
        SizedBox(
          height: 40,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: FiltroRapidoContaPagar.values.length,
            separatorBuilder: (_, _) => const SizedBox(width: 8),
            itemBuilder: (context, indice) {
              final opcao = FiltroRapidoContaPagar.values[indice];
              final selecionado = opcao == _filtro;

              return ChipFiltro(
                rotulo: opcao.rotulo,
                ligado: selecionado,
                aoTocar: () => setState(() => _filtro = opcao),
              );
            },
          ),
        ),
        const SizedBox(height: 4),
        Expanded(
          child: RefreshIndicator(
            onRefresh: () => ref.refresh(contasPagarProvider.future),
            child: contasAsync.when(
              loading: () => const SkeletonList(),
              error: (erro, _) => ListView(
                children: const [
                  SizedBox(height: 80),
                  Center(child: Text('Não foi possível carregar as contas.')),
                ],
              ),
              data: (todas) {
                final contas = todas
                    .where(_filtro.aplica)
                    .where((conta) => _combinaComBusca(conta, _busca))
                    .toList();

                if (contas.isEmpty) {
                  return ListView(
                    children: [
                      const SizedBox(height: 80),
                      Center(
                        child: Text(
                          todas.isEmpty
                              ? 'Nenhuma conta a pagar.'
                              : 'Nada encontrado com esse filtro.',
                        ),
                      ),
                    ],
                  );
                }

                return ListView(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                  children: [
                    for (final (status, doGrupo) in _agruparPorStatus(
                      contas,
                      statusVisual,
                    )) ...[
                      CabecalhoGrupo(
                        status.rotuloGrupo,
                        resumo: formatarMoeda(
                          doGrupo.fold<double>(0, (t, c) => t + c.valor),
                        ),
                      ),
                      ListaAgrupada(
                        recuo: 72,
                        linhas: [
                          for (final conta in doGrupo)
                            _LinhaContaPagar(conta: conta),
                        ],
                      ),
                    ],
                  ],
                );
              },
            ),
          ),
        ),
      ],
    );
  }
}

/// Agrupa mantendo a ordem de urgencia (vencidas primeiro).
List<(StatusVisualConta, List<T>)> _agruparPorStatus<T>(
  List<T> contas,
  StatusVisualConta Function(T) status,
) {
  return [
    for (final s in const [
      StatusVisualConta.vencida,
      StatusVisualConta.venceHoje,
      StatusVisualConta.aVencer,
      StatusVisualConta.paga,
      StatusVisualConta.cancelada,
    ])
      if (contas.where((c) => status(c) == s).toList() case final grupo
          when grupo.isNotEmpty)
        (s, grupo),
  ];
}

const _mesesCurtos = [
  'JAN',
  'FEV',
  'MAR',
  'ABR',
  'MAI',
  'JUN',
  'JUL',
  'AGO',
  'SET',
  'OUT',
  'NOV',
  'DEZ',
];

/// "Venceu ha 3 dias", "Vence amanha"... -- mais facil de ler de relance
/// que a data crua.
String _prazo(
  StatusVisualConta status,
  DateTime vencimento,
  DateTime? resolvidaEm,
) {
  final hoje = DateTime.now();
  final dias = DateTime(
    vencimento.year,
    vencimento.month,
    vencimento.day,
  ).difference(DateTime(hoje.year, hoje.month, hoje.day)).inDays;

  return switch (status) {
    StatusVisualConta.vencida =>
      dias == -1 ? 'Venceu ontem' : 'Venceu há ${-dias} dias',
    StatusVisualConta.venceHoje => 'Vence hoje',
    StatusVisualConta.aVencer =>
      dias == 1 ? 'Vence amanhã' : 'Vence em $dias dias',
    StatusVisualConta.paga =>
      resolvidaEm == null
          ? 'Quitada'
          : 'Quitada em ${formatarData(resolvidaEm).substring(0, 5)}',
    StatusVisualConta.cancelada => 'Cancelada',
  };
}

/// Bloco de data a esquerda da linha (dia grande + mes), na cor da
/// situacao -- o vencimento e a informacao que o dono procura primeiro.
class _BlocoData extends StatelessWidget {
  const _BlocoData({required this.data, required this.status});

  final DateTime data;
  final StatusVisualConta status;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    final urgente =
        status == StatusVisualConta.vencida ||
        status == StatusVisualConta.venceHoje;
    final cor = urgente ? status.cor : VertexColors.texto;
    final apagada =
        status == StatusVisualConta.paga ||
        status == StatusVisualConta.cancelada;

    return Container(
      width: 44,
      padding: const EdgeInsets.symmetric(vertical: 6),
      decoration: BoxDecoration(
        color: urgente ? status.corFundo : VertexColors.fundo,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        children: [
          Text(
            '${data.day}',
            style: tema.titleMedium?.copyWith(
              height: 1.1,
              fontWeight: FontWeight.w700,
              color: apagada ? VertexColors.textoTerciario : cor,
            ),
          ),
          Text(
            _mesesCurtos[data.month - 1],
            style: tema.labelSmall?.copyWith(
              fontSize: 9.5,
              color: apagada ? VertexColors.textoTerciario : cor,
            ),
          ),
        ],
      ),
    );
  }
}

class _LinhaConta extends StatelessWidget {
  const _LinhaConta({
    required this.status,
    required this.vencimento,
    required this.titulo,
    required this.detalhe,
    required this.valor,
    required this.aoTocar,
    this.acao,
  });

  final Widget? acao;
  final StatusVisualConta status;
  final DateTime vencimento;
  final String titulo;
  final String detalhe;
  final double valor;
  final VoidCallback aoTocar;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    final apagada =
        status == StatusVisualConta.paga ||
        status == StatusVisualConta.cancelada;
    final urgente =
        status == StatusVisualConta.vencida ||
        status == StatusVisualConta.venceHoje;

    return InkWell(
      onTap: aoTocar,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            _BlocoData(data: vencimento, status: status),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    titulo,
                    style: tema.titleSmall,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    detalhe,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: tema.bodySmall?.copyWith(
                      color: urgente ? status.cor : null,
                      fontWeight: urgente ? FontWeight.w600 : null,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  formatarMoeda(valor),
                  style: tema.titleSmall?.copyWith(
                    fontWeight: FontWeight.w700,
                    fontFeatures: const [FontFeature.tabularFigures()],
                    color: apagada ? VertexColors.textoTerciario : null,
                    decoration: status == StatusVisualConta.cancelada
                        ? TextDecoration.lineThrough
                        : null,
                  ),
                ),
                if (acao != null) ...[const SizedBox(height: 6), acao!],
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _LinhaContaPagar extends StatelessWidget {
  const _LinhaContaPagar({required this.conta});

  final ContaPagar conta;

  @override
  Widget build(BuildContext context) {
    final status = statusVisual(conta);

    return _LinhaConta(
      status: status,
      vencimento: conta.dataVencimento,
      titulo: conta.descricao ?? 'Despesa',
      detalhe: [
        _prazo(status, conta.dataVencimento, conta.dataPagamento),
        conta.categoria ?? '',
      ].where((p) => p.isNotEmpty).join(' · '),
      valor: conta.valor,
      acao: status == StatusVisualConta.paga
          ? null
          : _BotaoPagar(
              conta: conta,
              destaque: status == StatusVisualConta.vencida,
            ),
      aoTocar: () => showModalBottomSheet(
        context: context,
        isScrollControlled: true,
        builder: (context) => _DetalhesContaPagarSheet(conta: conta),
      ),
    );
  }
}

class _BotaoPagar extends StatelessWidget {
  const _BotaoPagar({required this.conta, required this.destaque});

  final ContaPagar conta;
  final bool destaque;

  @override
  Widget build(BuildContext context) {
    Future<void> pagar() async {
      final mensageiro = ScaffoldMessenger.of(context);
      final pago = await Navigator.of(context).push<bool>(
        MaterialPageRoute(
          builder: (_) => RealizarPagamentoScreen(conta: conta),
        ),
      );
      if (pago == true) {
        mensageiro.showSnackBar(
          const SnackBar(content: Text('Pagamento confirmado.')),
        );
      }
    }

    const tamanho = Size(0, 32);
    const espaco = EdgeInsets.symmetric(horizontal: 14);
    const texto = TextStyle(
      fontFamily: 'Figtree',
      fontSize: 13,
      fontWeight: FontWeight.w700,
    );

    if (destaque) {
      return FilledButton(
        style: FilledButton.styleFrom(
          minimumSize: tamanho,
          padding: espaco,
          textStyle: texto,
        ),
        onPressed: pagar,
        child: const Text('Pagar'),
      );
    }
    return OutlinedButton(
      style: OutlinedButton.styleFrom(
        minimumSize: tamanho,
        padding: espaco,
        textStyle: texto,
        foregroundColor: VertexColors.primaria,
        side: BorderSide(color: VertexColors.borda),
      ),
      onPressed: pagar,
      child: const Text('Pagar'),
    );
  }
}

/// Os 3 quadros do topo (Vencidas / Esta semana / Depois): resumo de
/// relance e, ao tocar, filtro da lista.
class _QuadrosResumo extends StatelessWidget {
  const _QuadrosResumo({
    required this.contas,
    required this.filtro,
    required this.aoEscolher,
  });

  final List<ContaPagar> contas;
  final FiltroRapidoContaPagar filtro;
  final ValueChanged<FiltroRapidoContaPagar> aoEscolher;

  @override
  Widget build(BuildContext context) {
    final vencidas = contas
        .where((c) => statusVisual(c) == StatusVisualConta.vencida)
        .toList();
    final semana = contas.where(_venceNaSemana).toList();
    final depois = contas
        .where(
          (c) =>
              statusVisual(c) == StatusVisualConta.aVencer &&
              !_venceNaSemana(c),
        )
        .toList();

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
      child: Row(
        children: [
          _Quadro(
            rotulo: 'Vencidas',
            contas: vencidas,
            ligado: filtro == FiltroRapidoContaPagar.vencidas,
            cor: VertexColors.erro,
            fundo: VertexColors.erroClaro,
            aoTocar: () => aoEscolher(FiltroRapidoContaPagar.vencidas),
          ),
          const SizedBox(width: 8),
          _Quadro(
            rotulo: 'Esta semana',
            contas: semana,
            ligado: filtro == FiltroRapidoContaPagar.estaSemana,
            cor: VertexColors.alertaTexto,
            fundo: VertexColors.alertaClaro,
            aoTocar: () => aoEscolher(FiltroRapidoContaPagar.estaSemana),
          ),
          const SizedBox(width: 8),
          _Quadro(
            rotulo: 'Depois',
            contas: depois,
            ligado: filtro == FiltroRapidoContaPagar.aVencer,
            cor: VertexColors.texto,
            fundo: VertexColors.card,
            borda: VertexColors.borda,
            aoTocar: () => aoEscolher(FiltroRapidoContaPagar.aVencer),
          ),
        ],
      ),
    );
  }
}

class _Quadro extends StatelessWidget {
  const _Quadro({
    required this.rotulo,
    required this.contas,
    required this.ligado,
    required this.cor,
    required this.fundo,
    required this.aoTocar,
    this.borda,
  });

  final String rotulo;
  final List<ContaPagar> contas;
  final bool ligado;
  final Color cor;
  final Color fundo;
  final Color? borda;
  final VoidCallback aoTocar;

  @override
  Widget build(BuildContext context) {
    final total = contas.fold<double>(0, (t, c) => t + c.valor);

    return Expanded(
      child: Material(
        color: fundo,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(
            color: ligado ? cor : (borda ?? fundo),
            width: ligado ? 1.5 : 1,
          ),
        ),
        child: InkWell(
          borderRadius: BorderRadius.circular(14),
          onTap: aoTocar,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  rotulo,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: cor,
                  ),
                ),
                Text(
                  '${contas.length}',
                  style: TextStyle(
                    fontFamily: VertexTheme.fonteDisplay,
                    fontSize: 22,
                    fontWeight: FontWeight.w700,
                    color: cor,
                  ),
                ),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(
                    formatarMoeda(total),
                    style: TextStyle(
                      fontSize: 12,
                      color: cor,
                      fontFeatures: const [FontFeature.tabularFigures()],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _DetalhesContaPagarSheet extends ConsumerWidget {
  const _DetalhesContaPagarSheet({required this.conta});

  final ContaPagar conta;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final status = statusVisual(conta);
    final paga = status == StatusVisualConta.paga;
    final cancelada = status == StatusVisualConta.cancelada;

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    conta.descricao ?? 'Despesa',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                StatusContaPill(status: status),
              ],
            ),
            const SizedBox(height: 16),
            const SizedBox(height: 4),
            Text(
              formatarMoeda(conta.valor),
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 12),
            _LinhaDetalhe('Categoria', conta.categoria ?? '—'),
            _LinhaDetalhe('Emissão', formatarData(conta.dataEmissao)),
            _LinhaDetalhe('Vencimento', formatarData(conta.dataVencimento)),
            if (conta.dataPagamento != null)
              _LinhaDetalhe('Pagamento', formatarData(conta.dataPagamento!)),
            _LinhaDetalhe('Nº do boleto', conta.numeroBoleto ?? '—'),
            if ((conta.observacao ?? '').isNotEmpty)
              _LinhaDetalhe('Observação', conta.observacao!),
            const SizedBox(height: 16),
            if (!paga && !cancelada)
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: () async {
                    final navegador = Navigator.of(context);
                    final mensageiro = ScaffoldMessenger.of(context);
                    navegador.pop();
                    final pago = await navegador.push<bool>(
                      MaterialPageRoute(
                        builder: (_) => RealizarPagamentoScreen(conta: conta),
                      ),
                    );
                    if (pago == true) {
                      mensageiro.showSnackBar(
                        const SnackBar(content: Text('Pagamento confirmado.')),
                      );
                    }
                  },
                  icon: const Icon(Icons.payments_outlined, size: 18),
                  label: const Text('Realizar pagamento'),
                ),
              ),
            if (conta.temComprovantePagamento)
              SizedBox(
                width: double.infinity,
                child: FilledButton.tonalIcon(
                  onPressed: () {
                    Navigator.of(context).pop();
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => ComprovanteScreen(conta: conta),
                      ),
                    );
                  },
                  icon: const Icon(Icons.check_circle_outline, size: 18),
                  label: const Text('Ver comprovante'),
                ),
              ),
            if (conta.temDocumento) ...[
              const SizedBox(height: 10),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: () async {
                    final erro = await ref
                        .read(financeiroActionsProvider)
                        .abrirDocumento(conta);

                    if (erro != null && context.mounted) {
                      ScaffoldMessenger.of(
                        context,
                      ).showSnackBar(SnackBar(content: Text(erro)));
                    }
                  },
                  icon: const Icon(Icons.description_outlined, size: 18),
                  label: const Text('Ver boleto'),
                ),
              ),
              const SizedBox(height: 10),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: () async {
                    Navigator.of(context).pop();
                    final erro = await ref
                        .read(financeiroActionsProvider)
                        .compartilharDocumento(conta);

                    if (erro != null && context.mounted) {
                      ScaffoldMessenger.of(
                        context,
                      ).showSnackBar(SnackBar(content: Text(erro)));
                    }
                  },
                  icon: const Icon(Icons.share_outlined, size: 18),
                  label: const Text('Compartilhar boleto'),
                ),
              ),
            ],
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () {
                  Navigator.of(context).pop();
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => HistoricoContaScreen(conta: conta),
                    ),
                  );
                },
                icon: const Icon(Icons.history, size: 18),
                label: const Text('Ver histórico'),
              ),
            ),
            if (!cancelada) ...[
              const SizedBox(height: 10),
              SizedBox(
                width: double.infinity,
                child: TextButton.icon(
                  onPressed: () => _confirmarCancelamento(context, ref),
                  style: TextButton.styleFrom(
                    foregroundColor: VertexColors.erro,
                  ),
                  icon: const Icon(Icons.cancel_outlined, size: 18),
                  label: const Text('Cancelar despesa'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Future<void> _confirmarCancelamento(
    BuildContext context,
    WidgetRef ref,
  ) async {
    final confirmar = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancelar despesa?'),
        content: Text(
          statusVisual(conta) == StatusVisualConta.paga
              ? 'Essa despesa já foi paga — cancelar uma despesa paga '
                    'exige aprovação de um administrador.'
              : 'Essa ação não pode ser desfeita.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Voltar'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: FilledButton.styleFrom(backgroundColor: VertexColors.erro),
            child: const Text('Cancelar despesa'),
          ),
        ],
      ),
    );

    if (confirmar != true || !context.mounted) return;

    Navigator.of(context).pop();

    final resultado = await ref
        .read(financeiroActionsProvider)
        .cancelarConta(conta.id);

    if (!context.mounted) return;

    if (resultado.erro != null) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(resultado.erro!)));
      return;
    }

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          resultado.aprovacaoPendente
              ? 'Pedido enviado — aguardando aprovação de um administrador.'
              : 'Despesa cancelada.',
        ),
      ),
    );
  }
}

class _LinhaDetalhe extends StatelessWidget {
  const _LinhaDetalhe(this.rotulo, this.valor);

  final String rotulo;
  final String valor;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 96,
            child: Text(
              rotulo,
              style: TextStyle(
                fontSize: 12.5,
                color: VertexColors.textoSecundario,
              ),
            ),
          ),
          Expanded(
            child: Text(
              valor,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}
