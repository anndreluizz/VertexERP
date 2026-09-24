import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../models/movimento_fiado.dart';
import '../../models/venda.dart';
import '../../theme/lista_agrupada.dart';
import '../../theme/skeleton.dart';
import '../../theme/vertex_colors.dart';
import '../clientes/cliente_detalhe_screen.dart';
import 'venda_detalhe_screen.dart';
import 'vendas_provider.dart';

class VendasScreen extends ConsumerWidget {
  const VendasScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final periodo = ref.watch(periodoVendasProvider);
    final atividadeAsync = ref.watch(atividadeVendasProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Vendas')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: PeriodoVendas.values.map((valor) {
                  final selecionado = valor == periodo;
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(valor.rotulo),
                      selected: selecionado,
                      onSelected: (_) =>
                          ref.read(periodoVendasProvider.notifier).state =
                              valor,
                    ),
                  );
                }).toList(),
              ),
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
                    Center(child: Text('Não foi possível carregar as vendas.')),
                  ],
                ),
                data: (itens) {
                  final filtrados = itens
                      .where((item) => periodo.contem(item.data))
                      .toList();

                  if (filtrados.isEmpty) {
                    return ListView(
                      children: const [
                        SizedBox(height: 80),
                        Center(child: Text('Nenhuma venda nesse período.')),
                      ],
                    );
                  }

                  // agrupa por dia (lista ja vem do mais recente pro
                  // mais antigo), com o total do dia no cabecalho
                  final grupos = <DateTime, List<ItemAtividadeVendas>>{};
                  for (final item in filtrados) {
                    final d = item.data;
                    grupos
                        .putIfAbsent(DateTime(d.year, d.month, d.day), () => [])
                        .add(item);
                  }

                  return ListView(
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                    children: [
                      for (final MapEntry(key: dia, value: doDia)
                          in grupos.entries) ...[
                        CabecalhoGrupo(
                          rotuloDia(dia),
                          resumo: formatarMoeda(
                            doDia.fold<double>(
                              0,
                              (soma, item) => soma + _valorEfetivo(item),
                            ),
                          ),
                        ),
                        ListaAgrupada(
                          linhas: [
                            for (final item in doDia)
                              switch (item) {
                                AtividadeVenda(:final venda) => _LinhaVenda(
                                  venda: venda,
                                ),
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
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}

double _valorEfetivo(ItemAtividadeVendas item) => switch (item) {
  AtividadeVenda(:final venda) =>
    venda.status == 'CANCELADA' ? 0 : venda.valorTotal,
  AtividadeRecebimento(:final movimento) => movimento.valor,
};

String _hora(DateTime d) =>
    '${d.hour.toString().padLeft(2, '0')}:${d.minute.toString().padLeft(2, '0')}';

/// Linha base das duas: hora a esquerda (coluna fixa, alinhada), titulo
/// e detalhe no meio, valor a direita.
class _Linha extends StatelessWidget {
  const _Linha({
    required this.hora,
    required this.titulo,
    required this.detalhe,
    required this.valor,
    required this.aoTocar,
    this.corValor,
    this.riscado = false,
  });

  final String hora;
  final String titulo;
  final String detalhe;
  final String valor;
  final VoidCallback aoTocar;
  final Color? corValor;
  final bool riscado;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;

    return InkWell(
      onTap: aoTocar,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        child: Row(
          children: [
            SizedBox(
              width: 48,
              child: Text(
                hora,
                style: tema.labelMedium?.copyWith(
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ),
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
                    style: tema.bodySmall,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            Text(
              valor,
              style: tema.titleSmall?.copyWith(
                fontWeight: FontWeight.w700,
                color: corValor,
                fontFeatures: const [FontFeature.tabularFigures()],
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
    final cancelada = venda.status == 'CANCELADA';
    final detalhe = [
      if (cancelada) 'Cancelada',
      formatarFormaPagamento(venda.formaPagamento),
      venda.usuarioNome ?? '',
    ].where((p) => p.isNotEmpty).join(' · ');

    return _Linha(
      hora: _hora(venda.data),
      titulo: 'Venda #${venda.id}',
      detalhe: detalhe,
      valor: formatarMoeda(venda.valorTotal),
      corValor: cancelada ? VertexColors.textoTerciario : null,
      riscado: cancelada,
      aoTocar: () => Navigator.of(context).push(
        MaterialPageRoute(
          builder: (context) => VendaDetalheScreen(venda: venda),
        ),
      ),
    );
  }
}

/// Recebimento de fiado (pagamento de uma compra a prazo ja feita) --
/// e dinheiro entrando, nao venda nova: valor em verde com "+", e o
/// toque leva pra ficha do cliente em vez do detalhe de uma venda.
class _LinhaRecebimento extends StatelessWidget {
  const _LinhaRecebimento({required this.movimento, required this.clienteNome});

  final MovimentoFiado movimento;
  final String clienteNome;

  @override
  Widget build(BuildContext context) {
    return _Linha(
      hora: _hora(movimento.data),
      titulo: clienteNome,
      detalhe: [
        'Recebimento de fiado',
        formatarFormaPagamento(movimento.formaPagamento),
      ].where((p) => p.isNotEmpty).join(' · '),
      valor: '+ ${formatarMoeda(movimento.valor)}',
      corValor: VertexColors.secundaria,
      aoTocar: () => Navigator.of(context).push(
        MaterialPageRoute(
          builder: (context) =>
              ClienteDetalheScreen(clienteId: movimento.clienteId),
        ),
      ),
    );
  }
}
