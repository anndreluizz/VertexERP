import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../theme/vertex_colors.dart';
import 'notificacoes_provider.dart';

class NotificacoesScreen extends ConsumerWidget {
  const NotificacoesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notificacoes = ref.watch(notificacoesProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Notificações')),
      body: notificacoes.isEmpty
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.notifications_none,
                      size: 40,
                      color: VertexColors.textoTerciario,
                    ),
                    const SizedBox(height: 12),
                    Text(
                      'Nenhuma notificação por enquanto.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: VertexColors.textoSecundario),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      'Boletos novos, pagamentos, comprovantes e '
                      'aprovações aparecem aqui em tempo real.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 12.5,
                        color: VertexColors.textoTerciario,
                      ),
                    ),
                  ],
                ),
              ),
            )
          : ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: notificacoes.length,
              separatorBuilder: (_, _) => const SizedBox(height: 8),
              itemBuilder: (context, indice) {
                final notificacao = notificacoes[indice];

                return Card(
                  margin: EdgeInsets.zero,
                  child: ListTile(
                    leading: const Icon(
                      Icons.notifications_outlined,
                      color: VertexColors.primaria,
                    ),
                    title: Text(notificacao.titulo),
                    subtitle: Text(notificacao.corpo),
                    trailing: Text(
                      formatarDataHora(notificacao.recebidaEm),
                      style: TextStyle(
                        fontSize: 10.5,
                        color: VertexColors.textoTerciario,
                      ),
                    ),
                  ),
                );
              },
            ),
    );
  }
}
