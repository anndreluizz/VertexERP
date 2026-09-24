import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../theme/lista_agrupada.dart';
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
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
        children: [
          _Perfil(
            nome: sessao.usuario?.nome ?? '',
            cargo: sessao.usuario?.cargo ?? '',
            loja: sessao.nomeLoja,
          ),
          const CabecalhoGrupo('Loja'),
          ListaAgrupada(
            recuo: 54,
            linhas: [
              _ItemMenu(
                icone: Icons.inventory_2_outlined,
                titulo: 'Estoque',
                subtitulo: 'Produtos críticos e sem estoque',
                aoTocar: () => _abrir(context, const EstoqueScreen()),
              ),
              _ItemMenu(
                icone: Icons.point_of_sale_outlined,
                titulo: 'Caixas',
                subtitulo: 'Status de todos os caixas da loja',
                aoTocar: () => _abrir(context, const CaixasScreen()),
              ),
              if (ehAdmin)
                _ItemMenu(
                  icone: Icons.rule_outlined,
                  titulo: 'Aprovações',
                  subtitulo: qtdAprovacoes == null
                      ? 'Pedidos que precisam da sua autorização'
                      : qtdAprovacoes == 0
                      ? 'Nenhum pedido pendente'
                      : '$qtdAprovacoes pedido(s) pendente(s)',
                  contador: qtdAprovacoes,
                  aoTocar: () => _abrir(context, const AprovacoesScreen()),
                ),
              _ItemMenu(
                icone: Icons.bar_chart_outlined,
                titulo: 'Relatórios',
                subtitulo: 'Resumo gerencial e PDF',
                aoTocar: () => _abrir(context, const RelatoriosScreen()),
              ),
            ],
          ),
          const CabecalhoGrupo('Conta'),
          ListaAgrupada(
            recuo: 54,
            linhas: [
              _ItemMenu(
                icone: Icons.notifications_outlined,
                titulo: 'Notificações',
                subtitulo: qtdNotificacoes == 0
                    ? 'Nenhuma por enquanto'
                    : '$qtdNotificacoes recebida(s) nesta sessão',
                contador: qtdNotificacoes,
                aoTocar: () => _abrir(context, const NotificacoesScreen()),
              ),
              _ItemMenu(
                icone: Icons.devices_outlined,
                titulo: 'Sessões',
                subtitulo: 'Aparelhos conectados à sua conta',
                aoTocar: () => _abrir(context, const SessoesScreen()),
              ),
            ],
          ),
          const SizedBox(height: 24),
          ListaAgrupada(
            recuo: 54,
            linhas: [
              _ItemMenu(
                icone: Icons.logout_rounded,
                titulo: 'Sair',
                perigo: true,
                aoTocar: () => _confirmarLogout(context, ref),
              ),
            ],
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
}

class _Perfil extends StatelessWidget {
  const _Perfil({required this.nome, required this.cargo, this.loja});

  final String nome;
  final String cargo;
  final String? loja;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    final partes = nome.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty);
    final iniciais = partes.isEmpty
        ? '?'
        : (partes.first[0] + (partes.length > 1 ? partes.last[0] : ''))
              .toUpperCase();

    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 8, 4, 4),
      child: Row(
        children: [
          Container(
            width: 52,
            height: 52,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: VertexColors.escuro
                  ? VertexColors.primariaClara
                  : VertexColors.sidebar,
              shape: BoxShape.circle,
            ),
            child: Text(
              iniciais,
              style: tema.titleMedium?.copyWith(
                color: Colors.white,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(nome, style: tema.titleMedium),
                const SizedBox(height: 2),
                Text(
                  [cargo, loja ?? ''].where((p) => p.isNotEmpty).join(' · '),
                  style: tema.bodySmall,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ItemMenu extends StatelessWidget {
  const _ItemMenu({
    required this.icone,
    required this.titulo,
    required this.aoTocar,
    this.subtitulo,
    this.contador,
    this.perigo = false,
  });

  final IconData icone;
  final String titulo;
  final String? subtitulo;
  final int? contador;
  final VoidCallback aoTocar;
  final bool perigo;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    final cor = perigo ? VertexColors.erro : VertexColors.textoSecundario;

    return InkWell(
      onTap: aoTocar,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        child: Row(
          children: [
            Icon(icone, size: 22, color: cor),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    titulo,
                    style: tema.titleSmall?.copyWith(
                      color: perigo ? VertexColors.erro : null,
                    ),
                  ),
                  if (subtitulo != null) ...[
                    const SizedBox(height: 2),
                    Text(subtitulo!, style: tema.bodySmall),
                  ],
                ],
              ),
            ),
            if ((contador ?? 0) > 0)
              Container(
                margin: const EdgeInsets.only(right: 6),
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: VertexColors.erro,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  '$contador',
                  style: tema.labelSmall?.copyWith(
                    color: Colors.white,
                    letterSpacing: 0,
                  ),
                ),
              ),
            if (!perigo)
              Icon(
                Icons.chevron_right_rounded,
                size: 20,
                color: VertexColors.textoTerciario,
              ),
          ],
        ),
      ),
    );
  }
}
