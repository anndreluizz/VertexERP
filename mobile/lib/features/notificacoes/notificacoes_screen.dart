import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../theme/lista_agrupada.dart';
import '../../theme/skeleton.dart';
import '../../theme/vertex_colors.dart';
import 'notificacoes_provider.dart';

class NotificacoesScreen extends ConsumerStatefulWidget {
  const NotificacoesScreen({super.key});

  @override
  ConsumerState<NotificacoesScreen> createState() => _NotificacoesScreenState();
}

class _NotificacoesScreenState extends ConsumerState<NotificacoesScreen> {
  @override
  void initState() {
    super.initState();
    // abriu a tela = viu tudo; o destaque de "nao lida" continua na lista
    // carregada agora (veio do servidor antes de marcar)
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await ref
          .read(notificacoesProvider.future)
          .catchError((_) => <Notificacao>[]);
      if (!mounted) return;
      await marcarTodasLidas(ref).catchError((_) {});
    });
  }

  @override
  Widget build(BuildContext context) {
    final notificacoesAsync = ref.watch(notificacoesProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Notificações')),
      body: RefreshIndicator(
        onRefresh: () => ref.refresh(notificacoesProvider.future),
        child: notificacoesAsync.when(
          loading: () => const SkeletonList(),
          error: (erro, _) => ListView(
            children: const [
              SizedBox(height: 80),
              Center(child: Text('Não foi possível carregar as notificações.')),
            ],
          ),
          data: (notificacoes) {
            if (notificacoes.isEmpty) return const _Vazio();

            final grupos = <DateTime, List<Notificacao>>{};
            for (final n in notificacoes) {
              final d = n.criadoEm;
              grupos
                  .putIfAbsent(DateTime(d.year, d.month, d.day), () => [])
                  .add(n);
            }

            return ListView(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
              children: [
                for (final MapEntry(key: dia, value: doDia)
                    in grupos.entries) ...[
                  CabecalhoGrupo(rotuloDia(dia)),
                  ListaAgrupada(
                    recuo: 54,
                    linhas: [
                      for (final n in doDia) _LinhaNotificacao(notificacao: n),
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

/// Icone e cor pelo titulo gravado no backend (NotificacaoService) --
/// sem campo de "tipo" no modelo, o titulo ja identifica o evento.
(IconData, Color) _visual(String titulo) {
  final t = titulo.toLowerCase();
  if (t.contains('fiado') || t.contains('haver')) {
    return (Icons.menu_book_outlined, VertexColors.alerta);
  }
  if (t.contains('venda')) {
    return (Icons.point_of_sale_outlined, VertexColors.primaria);
  }
  if (t.contains('recebid') || t.contains('pagamento')) {
    return (Icons.payments_outlined, VertexColors.secundaria);
  }
  if (t.contains('limite') ||
      t.contains('inadimplente') ||
      t.contains('venc') ||
      t.contains('acabando')) {
    return (Icons.warning_amber_rounded, VertexColors.erro);
  }
  return (Icons.notifications_none_rounded, VertexColors.textoSecundario);
}

class _LinhaNotificacao extends StatelessWidget {
  const _LinhaNotificacao({required this.notificacao});

  final Notificacao notificacao;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    final (icone, cor) = _visual(notificacao.titulo);
    final d = notificacao.criadoEm;
    final hora =
        '${d.hour.toString().padLeft(2, '0')}:${d.minute.toString().padLeft(2, '0')}';

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 1),
            child: Icon(icone, size: 22, color: cor),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        notificacao.titulo,
                        style: tema.titleSmall?.copyWith(
                          fontWeight: notificacao.lida
                              ? FontWeight.w600
                              : FontWeight.w700,
                        ),
                      ),
                    ),
                    Text(hora, style: tema.labelMedium),
                    if (!notificacao.lida) ...[
                      const SizedBox(width: 8),
                      Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(
                          color: VertexColors.primaria,
                          shape: BoxShape.circle,
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 3),
                Text(notificacao.corpo, style: tema.bodySmall),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Vazio extends StatelessWidget {
  const _Vazio();

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;

    // ListView (nao Center puro) pra o puxar-pra-atualizar funcionar
    return ListView(
      padding: const EdgeInsets.all(32),
      children: [
        const SizedBox(height: 60),
        Icon(
          Icons.notifications_none_rounded,
          size: 40,
          color: VertexColors.textoTerciario,
        ),
        const SizedBox(height: 12),
        Text(
          'Nenhuma notificação ainda.',
          textAlign: TextAlign.center,
          style: tema.titleSmall,
        ),
        const SizedBox(height: 6),
        Text(
          'Vendas, compras e pagamentos no fiado e contas recebidas '
          'aparecem aqui enquanto o app estiver aberto.',
          textAlign: TextAlign.center,
          style: tema.bodySmall,
        ),
      ],
    );
  }
}
