import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../models/movimento_fiado.dart';
import '../../models/venda.dart';
import '../../theme/componentes.dart';
import '../../theme/lista_agrupada.dart';
import '../../theme/skeleton.dart';
import '../../theme/vertex_colors.dart';
import '../../theme/vertex_theme.dart';
import '../clientes/cliente_detalhe_screen.dart';
import 'venda_detalhe_screen.dart';
import 'vendas_provider.dart';

/// Cor de cada forma de pagamento -- mesmas do caixa no Desktop
/// (frontend/design/widgets.py::_CORES_FORMA).
Color corFormaPagamento(String? forma) {
  final escuro = VertexColors.escuro;
  return switch (forma) {
    'DINHEIRO' => escuro ? const Color(0xFF4ADE80) : const Color(0xFF15803D),
    'PIX' => escuro ? const Color(0xFF2DD4BF) : const Color(0xFF0F766E),
    'DEBITO' ||
    'CARTAO' => escuro ? const Color(0xFF60A5FA) : const Color(0xFF1D4ED8),
    'CREDITO' => escuro ? const Color(0xFFA78BFA) : const Color(0xFF6D28D9),
    'PRAZO' ||
    'CHEQUE' ||
    'FIADO' => escuro ? const Color(0xFFFBBF24) : const Color(0xFFB45309),
    'TRANSFERENCIA' =>
      escuro ? const Color(0xFFF472B6) : const Color(0xFFBE185D),
    _ => VertexColors.primaria,
  };
}

const _periodos = [PeriodoVendas.hoje, PeriodoVendas.semana, PeriodoVendas.mes];

String _rotuloPeriodo(PeriodoVendas p) => switch (p) {
  PeriodoVendas.semana => '7 dias',
  _ => p.rotulo,
};

class VendasScreen extends ConsumerWidget {
  const VendasScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final periodo = ref.watch(periodoVendasProvider);
    final atividadeAsync = ref.watch(atividadeVendasProvider);

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            const CabecalhoTela(titulo: 'Vendas'),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              child: _SeletorPeriodo(
                atual: _periodos.contains(periodo)
                    ? periodo
                    : PeriodoVendas.hoje,
                aoEscolher: (p) =>
                    ref.read(periodoVendasProvider.notifier).state = p,
              ),
            ),
            Expanded(
              child: RefreshIndicator(
                onRefresh: () => ref.refresh(atividadeVendasProvider.future),
                child: atividadeAsync.when(
                  loading: () => const SkeletonList(),
                  error: (erro, _) => ListView(
                    children: const [
                      SizedBox(height: 80),
                      Center(
                        child: Text('Não foi possível carregar as vendas.'),
                      ),
                    ],
                  ),
                  data: (itens) => _Conteudo(
                    itens: itens,
                    periodo: _periodos.contains(periodo)
                        ? periodo
                        : PeriodoVendas.hoje,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SeletorPeriodo extends StatelessWidget {
  const _SeletorPeriodo({required this.atual, required this.aoEscolher});

  final PeriodoVendas atual;
  final ValueChanged<PeriodoVendas> aoEscolher;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: VertexColors.escuro
            ? VertexColors.card
            : const Color(0xFFEAE6DE),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          for (final p in _periodos)
            Expanded(
              child: Semantics(
                selected: p == atual,
                button: true,
                child: GestureDetector(
                  onTap: () => aoEscolher(p),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 160),
                    height: 38,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: p == atual
                          ? (VertexColors.escuro
                                ? VertexColors.primariaClara
                                : VertexColors.card)
                          : Colors.transparent,
                      borderRadius: BorderRadius.circular(9),
                      boxShadow: p == atual && !VertexColors.escuro
                          ? const [
                              BoxShadow(
                                color: Color(0x1A16213B),
                                blurRadius: 2,
                                offset: Offset(0, 1),
                              ),
                            ]
                          : null,
                    ),
                    child: Text(
                      _rotuloPeriodo(p),
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: p == atual
                            ? FontWeight.w700
                            : FontWeight.w600,
                        color: p == atual
                            ? VertexColors.texto
                            : VertexColors.textoSecundario,
                      ),
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

bool _cancelada(Venda v) => v.status == 'CANCELADA';

class _Conteudo extends StatelessWidget {
  const _Conteudo({required this.itens, required this.periodo});

  final List<ItemAtividadeVendas> itens;
  final PeriodoVendas periodo;

  @override
  Widget build(BuildContext context) {
    final doPeriodo = itens.where((i) => periodo.contem(i.data)).toList();
    final vendas = [
      for (final i in doPeriodo)
        if (i case AtividadeVenda(:final venda) when !_cancelada(venda)) venda,
    ];

    // comparacao so faz sentido pra "Hoje" (ontem esta na mesma lista)
    double? totalOntem;
    if (periodo == PeriodoVendas.hoje) {
      final agora = DateTime.now();
      final ontem = DateTime(agora.year, agora.month, agora.day - 1);
      totalOntem = 0;
      for (final i in itens) {
        if (i case AtividadeVenda(:final venda)
            when !_cancelada(venda) &&
                venda.data.year == ontem.year &&
                venda.data.month == ontem.month &&
                venda.data.day == ontem.day) {
          totalOntem = totalOntem! + venda.valorTotal;
        }
      }
    }

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
      children: [
        _Resumo(vendas: vendas, periodo: periodo, totalOntem: totalOntem),
        if (doPeriodo.isEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 48),
            child: Center(
              child: Text(
                'Nenhuma venda nesse período.',
                style: TextStyle(color: VertexColors.textoSecundario),
              ),
            ),
          )
        else
          for (final (titulo, grupo) in _agrupar(doPeriodo, periodo)) ...[
            CabecalhoGrupo(
              titulo,
              resumo: formatarMoeda(
                grupo.fold<double>(0, (s, i) => s + _valorEfetivo(i)),
              ),
            ),
            ListaAgrupada(
              recuo: 30,
              linhas: [
                for (final item in grupo)
                  switch (item) {
                    AtividadeVenda(:final venda) => _LinhaVenda(venda: venda),
                    AtividadeRecebimento(
                      :final movimento,
                      :final clienteNome,
                    ) =>
                      _LinhaRecebimento(
                        movimento: movimento,
                        clienteNome: clienteNome,
                      ),
                  },
              ],
            ),
          ],
      ],
    );
  }
}

/// Hoje: manha/tarde/noite. Outros periodos: um grupo por dia.
List<(String, List<ItemAtividadeVendas>)> _agrupar(
  List<ItemAtividadeVendas> itens,
  PeriodoVendas periodo,
) {
  final grupos = <String, List<ItemAtividadeVendas>>{};
  for (final item in itens) {
    final d = item.data;
    final chave = periodo == PeriodoVendas.hoje
        ? (d.hour < 12
              ? 'Manhã'
              : d.hour < 18
              ? 'Tarde'
              : 'Noite')
        : rotuloDia(d);
    grupos.putIfAbsent(chave, () => []).add(item);
  }
  return [for (final e in grupos.entries) (e.key, e.value)];
}

double _valorEfetivo(ItemAtividadeVendas item) => switch (item) {
  AtividadeVenda(:final venda) => _cancelada(venda) ? 0 : venda.valorTotal,
  AtividadeRecebimento(:final movimento) => movimento.valor,
};

class _Resumo extends StatelessWidget {
  const _Resumo({
    required this.vendas,
    required this.periodo,
    required this.totalOntem,
  });

  final List<Venda> vendas;
  final PeriodoVendas periodo;
  final double? totalOntem;

  @override
  Widget build(BuildContext context) {
    final total = vendas.fold<double>(0, (s, v) => s + v.valorTotal);

    // venda dividida em 2 formas conta cada parte na sua forma
    final porForma = <String, double>{};
    for (final v in vendas) {
      final parte2 = v.formaPagamento2 != null ? (v.valorForma2 ?? 0) : 0.0;
      porForma.update(
        v.formaPagamento,
        (x) => x + v.valorTotal - parte2,
        ifAbsent: () => v.valorTotal - parte2,
      );
      if (v.formaPagamento2 != null && parte2 > 0) {
        porForma.update(
          v.formaPagamento2!,
          (x) => x + parte2,
          ifAbsent: () => parte2,
        );
      }
    }
    final formas = porForma.entries.where((e) => e.value > 0).toList()
      ..sort((a, b) => b.value.compareTo(a.value));

    final rotulo = switch (periodo) {
      PeriodoVendas.hoje => 'Total de hoje',
      PeriodoVendas.semana => 'Últimos 7 dias',
      _ => 'Este mês',
    };
    final qtd = vendas.length;

    String? variacao;
    Color? corVariacao;
    if (totalOntem != null && totalOntem! > 0) {
      final pct = ((total - totalOntem!) / totalOntem! * 100).round();
      variacao = '${pct >= 0 ? '+' : ''}$pct% vs ontem';
      corVariacao = pct >= 0 ? VertexColors.sucesso : VertexColors.erro;
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: VertexColors.card,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: VertexColors.borda),
      ),
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
                      '$rotulo · $qtd ${qtd == 1 ? 'venda' : 'vendas'}',
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
                          fontSize: 30,
                          fontWeight: FontWeight.w700,
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
                  fundo: corVariacao == VertexColors.sucesso
                      ? VertexColors.sucessoClaro
                      : VertexColors.erroClaro,
                  cor: corVariacao!,
                ),
            ],
          ),
          if (formas.isNotEmpty && total > 0) ...[
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: SizedBox(
                height: 12,
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    for (var i = 0; i < formas.length; i++) ...[
                      if (i > 0) const SizedBox(width: 2),
                      Expanded(
                        flex: (formas[i].value / total * 1000).round().clamp(
                          1,
                          1000,
                        ),
                        child: ColoredBox(
                          color: corFormaPagamento(formas[i].key),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            Wrap(
              runSpacing: 8,
              children: [
                for (final f in formas)
                  FractionallySizedBox(
                    widthFactor: 1,
                    child: Padding(
                      padding: const EdgeInsets.only(right: 12),
                      child: Row(
                        children: [
                          Container(
                            width: 10,
                            height: 10,
                            decoration: BoxDecoration(
                              color: corFormaPagamento(f.key),
                              borderRadius: BorderRadius.circular(3),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              formatarFormaPagamento(f.key),
                              style: const TextStyle(fontSize: 13.5),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          Text(
                            formatarMoeda(f.value),
                            style: const TextStyle(
                              fontSize: 13.5,
                              fontWeight: FontWeight.w700,
                              fontFeatures: tabular,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

String _hora(DateTime d) =>
    '${d.hour.toString().padLeft(2, '0')}:${d.minute.toString().padLeft(2, '0')}';

class _Linha extends StatelessWidget {
  const _Linha({
    required this.corFaixa,
    required this.titulo,
    required this.detalhe,
    required this.valor,
    required this.aoTocar,
    this.corValor,
    this.corDetalhe,
    this.riscado = false,
  });

  final Color corFaixa;
  final String titulo;
  final String detalhe;
  final String valor;
  final VoidCallback aoTocar;
  final Color? corValor;
  final Color? corDetalhe;
  final bool riscado;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: aoTocar,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
        child: Row(
          children: [
            Container(
              width: 4,
              height: 36,
              decoration: BoxDecoration(
                color: corFaixa,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    titulo,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 14.5,
                      fontWeight: FontWeight.w600,
                      color: riscado ? VertexColors.textoSecundario : null,
                      decoration: riscado ? TextDecoration.lineThrough : null,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    detalhe,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 12.5,
                      color: corDetalhe ?? VertexColors.textoSecundario,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            Text(
              valor,
              style: TextStyle(
                fontSize: 14.5,
                fontWeight: FontWeight.w700,
                fontFeatures: tabular,
                color: riscado ? VertexColors.textoSecundario : corValor,
                decoration: riscado ? TextDecoration.lineThrough : null,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LinhaVenda extends StatelessWidget {
  const _LinhaVenda({required this.venda});

  final Venda venda;

  @override
  Widget build(BuildContext context) {
    final cancelada = _cancelada(venda);
    final qtdItens = venda.itens.fold<int>(0, (s, i) => s + i.quantidade);
    final formas = [
      formatarFormaPagamento(venda.formaPagamento),
      if (venda.formaPagamento2 != null)
        formatarFormaPagamento(venda.formaPagamento2),
    ].join(' + ');
    final detalhe = cancelada
        ? '${_hora(venda.data)} · cancelada'
        : [
            _hora(venda.data),
            if (qtdItens > 0) '$qtdItens ${qtdItens == 1 ? 'item' : 'itens'}',
            formas,
            venda.usuarioNome ?? '',
          ].where((p) => p.isNotEmpty).join(' · ');

    return _Linha(
      corFaixa: cancelada
          ? VertexColors.erro
          : corFormaPagamento(venda.formaPagamento),
      titulo: 'Venda #${venda.id}',
      detalhe: detalhe,
      corDetalhe: cancelada ? VertexColors.erro : null,
      valor: formatarMoeda(venda.valorTotal),
      riscado: cancelada,
      aoTocar: () => Navigator.of(context).push(
        MaterialPageRoute(
          builder: (context) => VendaDetalheScreen(venda: venda),
        ),
      ),
    );
  }
}

/// Recebimento de fiado: dinheiro entrando, nao venda nova -- valor em
/// verde com "+", e o toque leva pra ficha do cliente.
class _LinhaRecebimento extends StatelessWidget {
  const _LinhaRecebimento({required this.movimento, required this.clienteNome});

  final MovimentoFiado movimento;
  final String clienteNome;

  @override
  Widget build(BuildContext context) {
    return _Linha(
      corFaixa: VertexColors.sucesso,
      titulo: clienteNome,
      detalhe: [
        _hora(movimento.data),
        'Recebeu fiado',
        formatarFormaPagamento(movimento.formaPagamento),
      ].where((p) => p.isNotEmpty).join(' · '),
      valor: '+ ${formatarMoeda(movimento.valor)}',
      corValor: VertexColors.sucesso,
      aoTocar: () => Navigator.of(context).push(
        MaterialPageRoute(
          builder: (context) =>
              ClienteDetalheScreen(clienteId: movimento.clienteId),
        ),
      ),
    );
  }
}
