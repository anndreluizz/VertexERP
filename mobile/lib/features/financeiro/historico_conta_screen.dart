import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../models/conta_pagar.dart';
import '../../models/conta_pagar_evento.dart';
import '../../theme/vertex_colors.dart';
import 'financeiro_provider.dart';

/// Linha do tempo de auditoria de uma despesa -- quem fez o que e
/// quando (criada, boleto anexado, paga, comprovante...). So cresce,
/// nunca é editada -- por isso a tela e so leitura.
class HistoricoContaScreen extends ConsumerWidget {
  const HistoricoContaScreen({super.key, required this.conta});

  final ContaPagar conta;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final eventosAsync = ref.watch(eventosContaProvider(conta.id));

    return Scaffold(
      appBar: AppBar(title: const Text('Histórico')),
      body: SafeArea(
        child: eventosAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (erro, _) => const Center(
            child: Text('Não foi possível carregar o histórico.'),
          ),
          data: (eventos) {
            if (eventos.isEmpty) {
              return const Center(
                child: Text('Nenhum evento registrado ainda.'),
              );
            }

            return ListView.builder(
              padding: const EdgeInsets.all(20),
              itemCount: eventos.length,
              itemBuilder: (context, indice) {
                final evento = eventos[indice];
                final ultimo = indice == eventos.length - 1;

                return _LinhaEvento(evento: evento, ultimo: ultimo);
              },
            );
          },
        ),
      ),
    );
  }
}

Color _corDoEvento(String tipo) => switch (tipo) {
  'PAGA' => VertexColors.secundaria,
  'CANCELAMENTO_SOLICITADO' => VertexColors.alerta,
  'CANCELADA' => VertexColors.erro,
  _ => VertexColors.primaria,
};

IconData _iconeDoEvento(String tipo) => switch (tipo) {
  'CRIADA' => Icons.add_circle_outline,
  'DOCUMENTO_ANEXADO' => Icons.description_outlined,
  'PAGA' => Icons.check_circle_outline,
  'COMPROVANTE_ANEXADO' || 'COMPROVANTE_TROCADO' => Icons.receipt_long_outlined,
  'CANCELAMENTO_SOLICITADO' => Icons.hourglass_empty,
  'CANCELADA' => Icons.cancel_outlined,
  _ => Icons.circle_outlined,
};

class _LinhaEvento extends StatelessWidget {
  const _LinhaEvento({required this.evento, required this.ultimo});

  final ContaPagarEvento evento;
  final bool ultimo;

  @override
  Widget build(BuildContext context) {
    final cor = _corDoEvento(evento.tipo);

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            children: [
              Container(
                width: 30,
                height: 30,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: cor.withValues(alpha: 0.12),
                  shape: BoxShape.circle,
                ),
                child: Icon(_iconeDoEvento(evento.tipo), size: 16, color: cor),
              ),
              if (!ultimo)
                Expanded(
                  child: Container(width: 1.5, color: VertexColors.borda),
                ),
            ],
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(bottom: ultimo ? 0 : 22, top: 4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    evento.rotulo,
                    style: const TextStyle(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '${formatarDataHora(evento.data)}'
                    '${evento.usuarioNome != null ? ' · ${evento.usuarioNome}' : ''}'
                    '${evento.dispositivo != null ? ' · ${evento.dispositivo}' : ''}',
                    style: TextStyle(
                      fontSize: 11.5,
                      color: VertexColors.textoSecundario,
                    ),
                  ),
                  if (evento.detalhes != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      evento.detalhes!,
                      style: TextStyle(
                        fontSize: 12,
                        color: VertexColors.textoSecundario,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
