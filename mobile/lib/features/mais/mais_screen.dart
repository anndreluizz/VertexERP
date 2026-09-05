import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../theme/vertex_colors.dart';
import '../aprovacoes/aprovacoes_provider.dart';
import '../aprovacoes/aprovacoes_screen.dart';
import '../caixas/caixas_screen.dart';
import '../estoque/estoque_screen.dart';
import '../notificacoes/notificacoes_provider.dart';
import '../notificacoes/notificacoes_screen.dart';
import '../relatorios/relatorios_screen.dart';
import '../sessoes/sessoes_screen.dart';

/// Modulos usados com menos frequencia que os 4 da barra inferior —
/// evita lotar a barra conforme o app cresce (o roteiro completo tem
/// mais telas planejadas: Perfil, Configuracoes...).
class MaisScreen extends ConsumerWidget {
  const MaisScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sessao = ref.watch(sessaoControllerProvider);
    final qtdNotificacoes = ref.watch(notificacoesProvider).length;
    final ehAdmin = sessao.usuario?.admin ?? false;

    // Endpoint de aprovacoes e restrito a admin -- pedir a lista pra
    // quem nao e so ia devolver 403 sem necessidade.
    final qtdAprovacoes = ehAdmin
        ? ref.watch(aprovacoesPendentesProvider).valueOrNull?.length
        : null;

    return Scaffold(
      appBar: AppBar(title: const Text('Mais')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 22,
                    backgroundColor: VertexColors.primariaClara,
                    child: Text(
                      (sessao.usuario?.nome.isNotEmpty ?? false)
                          ? sessao.usuario!.nome[0].toUpperCase()
                          : '?',
                      style: const TextStyle(
                        color: VertexColors.primaria,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          sessao.usuario?.nome ?? '',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        Text(
                          sessao.usuario?.cargo ?? '',
                          style: TextStyle(
                            fontSize: 12.5,
                            color: VertexColors.textoSecundario,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 18),
          _itemMenu(
            context,
            icone: Icons.inventory_2_outlined,
            titulo: 'Estoque',
            subtitulo: 'Produtos críticos e sem estoque',
            aoTocar: () => _abrir(context, const EstoqueScreen()),
          ),
          _itemMenu(
            context,
            icone: Icons.point_of_sale_outlined,
            titulo: 'Caixas',
            subtitulo: 'Status de todos os caixas da loja',
            aoTocar: () => _abrir(context, const CaixasScreen()),
          ),
          if (ehAdmin)
            _itemMenu(
              context,
              icone: Icons.rule_outlined,
              titulo: 'Aprovações',
              subtitulo: qtdAprovacoes == null
                  ? 'Pedidos que precisam da sua autorização'
                  : qtdAprovacoes == 0
                  ? 'Nenhum pedido pendente'
                  : '$qtdAprovacoes pedido(s) pendente(s)',
              aoTocar: () => _abrir(context, const AprovacoesScreen()),
            ),
          _itemMenu(
            context,
            icone: Icons.bar_chart_outlined,
            titulo: 'Relatórios',
            subtitulo: 'Resumo gerencial e exportação em PDF',
            aoTocar: () => _abrir(context, const RelatoriosScreen()),
          ),
          _itemMenu(
            context,
            icone: Icons.notifications_outlined,
            titulo: 'Notificações',
            subtitulo: qtdNotificacoes == 0
                ? 'Nenhuma por enquanto'
                : '$qtdNotificacoes recebida(s) nesta sessão',
            aoTocar: () => _abrir(context, const NotificacoesScreen()),
          ),
          _itemMenu(
            context,
            icone: Icons.devices_outlined,
            titulo: 'Sessões',
            subtitulo: 'Aparelhos conectados à sua conta',
            aoTocar: () => _abrir(context, const SessoesScreen()),
          ),
          const SizedBox(height: 18),
          _itemMenu(
            context,
            icone: Icons.logout,
            titulo: 'Sair',
            subtitulo: 'Encerrar sessão neste aparelho',
            perigo: true,
            aoTocar: () => _confirmarLogout(context, ref),
          ),
        ],
      ),
    );
  }

  Future<void> _confirmarLogout(BuildContext context, WidgetRef ref) async {
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

    if (confirmar != true) return;

    ref.read(sessaoControllerProvider.notifier).logout();
  }

  void _abrir(BuildContext context, Widget tela) {
    Navigator.of(context).push(MaterialPageRoute(builder: (context) => tela));
  }

  Widget _itemMenu(
    BuildContext context, {
    required IconData icone,
    required String titulo,
    required String subtitulo,
    required VoidCallback aoTocar,
    bool perigo = false,
  }) {
    final cor = perigo ? VertexColors.erro : VertexColors.primaria;

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        onTap: aoTocar,
        leading: Container(
          width: 38,
          height: 38,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: cor.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(11),
          ),
          child: Icon(icone, size: 18, color: cor),
        ),
        title: Text(titulo),
        subtitle: Text(subtitulo),
        trailing: const Icon(
          Icons.chevron_right,
          color: VertexColors.textoTerciario,
        ),
      ),
    );
  }
}
