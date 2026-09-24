import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../models/caixa.dart';
import '../../theme/lista_agrupada.dart';
import '../../theme/vertex_colors.dart';
import 'caixas_provider.dart';

String _formatarDuracao(Duration duracao) {
  final horas = duracao.inHours;
  final minutos = duracao.inMinutes % 60;

  if (horas <= 0) return '${minutos}min';
  return '${horas}h ${minutos}min';
}

class CaixasScreen extends ConsumerWidget {
  const CaixasScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final caixasAsync = ref.watch(caixasProvider);
    final operadoresAsync = ref.watch(operadoresLookupProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Caixas')),
      body: RefreshIndicator(
        onRefresh: () => ref.refresh(caixasProvider.future),
        child: caixasAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (erro, _) => ListView(
            children: const [
              SizedBox(height: 80),
              Center(child: Text('Não foi possível carregar os caixas.')),
            ],
          ),
          data: (caixas) {
            final operadores = operadoresAsync.value ?? const {};

            final abertos = caixas.where((c) => c.aberto).toList();
            final fechados = caixas.where((c) => !c.aberto).toList();

            if (caixas.isEmpty) {
              return ListView(
                children: const [
                  SizedBox(height: 80),
                  Center(child: Text('Nenhum caixa registrado ainda.')),
                ],
              );
            }

            return ListView(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
              children: [
                CabecalhoGrupo(
                  'Abertos agora',
                  resumo: abertos.isEmpty ? null : '${abertos.length}',
                ),
                if (abertos.isEmpty)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(4, 0, 4, 4),
                    child: Text(
                      'Nenhum caixa aberto no momento.',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  )
                else
                  ListaAgrupada(
                    recuo: 38,
                    linhas: [
                      for (final caixa in abertos)
                        _LinhaCaixa(
                          caixa: caixa,
                          nomeOperador: operadores[caixa.usuarioId],
                        ),
                    ],
                  ),
                if (fechados.isNotEmpty) ...[
                  const CabecalhoGrupo('Fechados recentemente'),
                  ListaAgrupada(
                    recuo: 38,
                    linhas: [
                      for (final caixa in fechados)
                        _LinhaCaixa(
                          caixa: caixa,
                          nomeOperador: operadores[caixa.usuarioId],
                        ),
                    ],
                  ),
                ],
              ],
            );
          },
        ),
      ),
    );
  }
}

class _LinhaCaixa extends StatelessWidget {
  const _LinhaCaixa({required this.caixa, this.nomeOperador});

  final Caixa caixa;
  final String? nomeOperador;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          // ponto verde = aberto agora (mesmo sinal do Desktop)
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: caixa.aberto
                  ? VertexColors.sucesso
                  : VertexColors.bordaForte,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  nomeOperador ?? 'Operador #${caixa.usuarioId ?? '-'}',
                  style: tema.titleSmall,
                ),
                const SizedBox(height: 2),
                Text(
                  caixa.aberto
                      ? 'Aberto há ${_formatarDuracao(caixa.tempoAberto)}'
                      : 'Fechado ${rotuloDia(caixa.dataFechamento!).toLowerCase()}'
                            ' às ${formatarDataHora(caixa.dataFechamento!).substring(11)}',
                  style: tema.bodySmall,
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                formatarMoeda(caixa.saldoFinal),
                style: tema.titleSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
              const SizedBox(height: 2),
              Text(
                caixa.aberto ? 'em caixa' : 'no fechamento',
                style: tema.bodySmall,
              ),
            ],
          ),
        ],
      ),
    );
  }
}
