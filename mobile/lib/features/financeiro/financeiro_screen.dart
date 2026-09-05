import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../models/conta_pagar.dart';
import '../../models/conta_receber.dart';
import '../../theme/skeleton.dart';
import '../../theme/vertex_colors.dart';
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
      ref.invalidate(contasReceberProvider);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Financeiro'),
          bottom: const TabBar(
            tabs: [
              Tab(text: 'A Pagar'),
              Tab(text: 'A Receber'),
            ],
          ),
        ),
        body: const TabBarView(
          children: [_AbaContasPagar(), _AbaContasReceber()],
        ),
      ),
    );
  }
}

/// Vencido ou vencendo em ate 1 dia esquenta a cor — mesmo criterio
/// usado na tela de Contas a Pagar do Desktop.
Color _corVencimento(DateTime vencimento, bool resolvida) {
  if (resolvida) return VertexColors.textoSecundario;

  final dias = vencimento.difference(DateTime.now()).inDays;
  return dias <= 1 ? VertexColors.erro : VertexColors.texto;
}

/// Filtros rapidos da aba "A Pagar" -- cada um e um recorte simples
/// por cima da mesma lista ja carregada, sem ida nova ao servidor.
enum FiltroRapidoContaPagar {
  todas,
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

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
          child: TextField(
            controller: _buscaController,
            onChanged: (valor) => setState(() => _busca = valor),
            decoration: InputDecoration(
              hintText: 'Buscar por descrição, categoria, boleto...',
              prefixIcon: const Icon(Icons.search, size: 20),
              isDense: true,
              suffixIcon: _busca.isEmpty
                  ? null
                  : IconButton(
                      icon: const Icon(Icons.close, size: 18),
                      onPressed: () => setState(() {
                        _buscaController.clear();
                        _busca = '';
                      }),
                    ),
              contentPadding: const EdgeInsets.symmetric(vertical: 10),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
          ),
        ),
        SizedBox(
          height: 36,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: FiltroRapidoContaPagar.values.length,
            separatorBuilder: (_, _) => const SizedBox(width: 8),
            itemBuilder: (context, indice) {
              final opcao = FiltroRapidoContaPagar.values[indice];
              final selecionado = opcao == _filtro;

              return ChoiceChip(
                label: Text(opcao.rotulo),
                selected: selecionado,
                labelStyle: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: selecionado ? Colors.white : VertexColors.texto,
                ),
                selectedColor: VertexColors.primaria,
                backgroundColor: VertexColors.card,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(999),
                  side: BorderSide(
                    color: selecionado
                        ? VertexColors.primaria
                        : VertexColors.borda,
                  ),
                ),
                onSelected: (_) => setState(() => _filtro = opcao),
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

                return ListView.separated(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
                  itemCount: contas.length,
                  separatorBuilder: (_, _) => const SizedBox(height: 10),
                  itemBuilder: (context, indice) =>
                      _CartaoContaPagar(conta: contas[indice]),
                );
              },
            ),
          ),
        ),
      ],
    );
  }
}

class _CartaoContaPagar extends ConsumerWidget {
  const _CartaoContaPagar({required this.conta});

  final ContaPagar conta;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final status = statusVisual(conta);
    final paga = status == StatusVisualConta.paga;

    return Card(
      margin: EdgeInsets.zero,
      color: paga ? VertexColors.sucessoClaro : null,
      shape: paga
          ? RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: const BorderSide(
                color: VertexColors.secundaria,
                width: 1.5,
              ),
            )
          : null,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Text(
                    conta.descricao ?? 'Despesa',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                Text(
                  formatarMoeda(conta.valor),
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                IconButton(
                  visualDensity: VisualDensity.compact,
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(
                    minWidth: 32,
                    minHeight: 32,
                  ),
                  icon: const Icon(Icons.more_vert, size: 19),
                  onPressed: () => _abrirMaisOpcoes(context, ref),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Row(
              children: [
                StatusContaPill(status: status),
                if ((conta.categoria ?? '').isNotEmpty) ...[
                  const SizedBox(width: 6),
                  Text(
                    conta.categoria!,
                    style: TextStyle(
                      fontSize: 11.5,
                      color: VertexColors.textoSecundario,
                    ),
                  ),
                ],
              ],
            ),
            const SizedBox(height: 6),
            Text(
              'Vencimento: ${formatarData(conta.dataVencimento)}',
              style: TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: 12.5,
                color: _corVencimento(conta.dataVencimento, paga),
              ),
            ),
            if (conta.temDocumento || conta.temComprovantePagamento || !paga) ...[
              const SizedBox(height: 10),
              Wrap(
                alignment: WrapAlignment.end,
                spacing: 4,
                children: [
                  if (conta.temDocumento)
                    TextButton.icon(
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
                      icon: const Icon(Icons.description_outlined, size: 16),
                      label: const Text('Ver boleto'),
                    ),
                  if (conta.temComprovantePagamento)
                    TextButton.icon(
                      onPressed: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => ComprovanteScreen(conta: conta),
                        ),
                      ),
                      icon: const Icon(Icons.check_circle_outline, size: 16),
                      label: const Text('Ver comprovante'),
                    ),
                  if (!paga)
                    FilledButton(
                      onPressed: () async {
                        final pago = await Navigator.of(context).push<bool>(
                          MaterialPageRoute(
                            builder: (_) =>
                                RealizarPagamentoScreen(conta: conta),
                          ),
                        );

                        if (pago == true && context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Pagamento confirmado.'),
                            ),
                          );
                        }
                      },
                      child: const Text('Realizar pagamento'),
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  void _abrirMaisOpcoes(BuildContext context, WidgetRef ref) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(18)),
      ),
      builder: (context) => _DetalhesContaPagarSheet(conta: conta),
    );
  }
}

class _DetalhesContaPagarSheet extends ConsumerWidget {
  const _DetalhesContaPagarSheet({required this.conta});

  final ContaPagar conta;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final status = statusVisual(conta);

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 36,
                height: 4,
                margin: const EdgeInsets.only(bottom: 16),
                decoration: BoxDecoration(
                  color: VertexColors.borda,
                  borderRadius: BorderRadius.circular(999),
                ),
              ),
            ),
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
            _LinhaDetalhe('Valor', formatarMoeda(conta.valor)),
            _LinhaDetalhe('Categoria', conta.categoria ?? '—'),
            _LinhaDetalhe('Emissão', formatarData(conta.dataEmissao)),
            _LinhaDetalhe('Vencimento', formatarData(conta.dataVencimento)),
            if (conta.dataPagamento != null)
              _LinhaDetalhe('Pagamento', formatarData(conta.dataPagamento!)),
            _LinhaDetalhe('Nº do boleto', conta.numeroBoleto ?? '—'),
            if ((conta.observacao ?? '').isNotEmpty)
              _LinhaDetalhe('Observação', conta.observacao!),
            if (conta.temDocumento) ...[
              const SizedBox(height: 12),
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
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: TextButton.icon(
                onPressed: () => _confirmarCancelamento(context, ref),
                style: TextButton.styleFrom(foregroundColor: VertexColors.erro),
                icon: const Icon(Icons.cancel_outlined, size: 18),
                label: const Text('Cancelar despesa'),
              ),
            ),
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
            style: FilledButton.styleFrom(
              backgroundColor: VertexColors.erro,
            ),
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

class _AbaContasReceber extends ConsumerWidget {
  const _AbaContasReceber();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final contasAsync = ref.watch(contasReceberProvider);

    return RefreshIndicator(
      onRefresh: () => ref.refresh(contasReceberProvider.future),
      child: contasAsync.when(
        loading: () => const SkeletonList(),
        error: (erro, _) => ListView(
          children: const [
            SizedBox(height: 80),
            Center(child: Text('Não foi possível carregar as contas.')),
          ],
        ),
        data: (contas) {
          if (contas.isEmpty) {
            return ListView(
              children: const [
                SizedBox(height: 80),
                Center(child: Text('Nenhuma conta a receber.')),
              ],
            );
          }

          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: contas.length,
            separatorBuilder: (_, _) => const SizedBox(height: 10),
            itemBuilder: (context, indice) =>
                _CartaoContaReceber(conta: contas[indice]),
          );
        },
      ),
    );
  }
}

class _CartaoContaReceber extends ConsumerWidget {
  const _CartaoContaReceber({required this.conta});

  final ContaReceber conta;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final recebida = conta.status == 'RECEBIDO';

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Cliente #${conta.clienteId}',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                Text(
                  formatarMoeda(conta.valor),
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ],
            ),
            const SizedBox(height: 3),
            Text(
              'Vencimento: ${formatarData(conta.dataVencimento)}',
              style: TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: 12.5,
                color: _corVencimento(conta.dataVencimento, recebida),
              ),
            ),
            if (!recebida) ...[
              const SizedBox(height: 10),
              Align(
                alignment: Alignment.centerRight,
                child: OutlinedButton(
                  onPressed: () => _confirmarRecebimento(context, ref),
                  child: const Text('Marcar como recebida'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Future<void> _confirmarRecebimento(
    BuildContext context,
    WidgetRef ref,
  ) async {
    final confirmar = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Marcar como recebida?'),
        content: Text(
          'Confirma o recebimento de ${formatarMoeda(conta.valor)} do '
          'Cliente #${conta.clienteId}? Essa ação não pode ser desfeita '
          'pelo app.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Voltar'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Marcar como recebida'),
          ),
        ],
      ),
    );

    if (confirmar != true || !context.mounted) return;

    final erro = await ref.read(financeiroActionsProvider).receberConta(conta.id);

    if (erro != null && context.mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(erro)));
    }
  }
}
