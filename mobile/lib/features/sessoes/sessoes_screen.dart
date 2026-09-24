import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../models/sessao.dart';
import '../../theme/lista_agrupada.dart';
import '../../theme/vertex_colors.dart';
import 'sessoes_provider.dart';

class SessoesScreen extends ConsumerWidget {
  const SessoesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sessoesAsync = ref.watch(sessoesProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Sessões')),
      body: RefreshIndicator(
        onRefresh: () => ref.refresh(sessoesProvider.future),
        child: sessoesAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (erro, _) => ListView(
            children: const [
              SizedBox(height: 80),
              Center(child: Text('Não foi possível carregar as sessões.')),
            ],
          ),
          data: (sessoes) {
            return ListView(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
              children: [
                Text(
                  'Aparelhos com sessão aberta na sua conta. Encerre '
                  'qualquer uma remotamente se não reconhecer ou não '
                  'usar mais um deles.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 4),
                CabecalhoGrupo(
                  '${sessoes.length} aparelho'
                  '${sessoes.length == 1 ? '' : 's'}',
                ),
                ListaAgrupada(
                  recuo: 54,
                  linhas: [
                    for (final sessao in sessoes) _CartaoSessao(sessao: sessao),
                  ],
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _CartaoSessao extends ConsumerStatefulWidget {
  const _CartaoSessao({required this.sessao});

  final Sessao sessao;

  @override
  ConsumerState<_CartaoSessao> createState() => _CartaoSessaoState();
}

class _CartaoSessaoState extends ConsumerState<_CartaoSessao> {
  bool _encerrando = false;

  Future<void> _encerrar() async {
    final confirmar = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Encerrar sessão?'),
        content: const Text(
          'O aparelho vai precisar fazer login de novo pra acessar a conta.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancelar'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Encerrar'),
          ),
        ],
      ),
    );

    if (confirmar != true) return;

    setState(() => _encerrando = true);

    final erro = await ref
        .read(sessoesActionsProvider)
        .revogar(widget.sessao.id);

    if (!mounted) return;

    setState(() => _encerrando = false);

    if (erro != null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(erro)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final sessao = widget.sessao;
    final tema = Theme.of(context).textTheme;
    final nome = sessao.dispositivo ?? 'Aparelho desconhecido';
    final computador = RegExp(
      r'windows|desktop|mac|linux|pc\b',
      caseSensitive: false,
    ).hasMatch(nome);

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 8, 10),
      child: Row(
        children: [
          Icon(
            computador ? Icons.computer_outlined : Icons.smartphone_outlined,
            size: 22,
            color: VertexColors.textoSecundario,
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(nome, style: tema.titleSmall),
                const SizedBox(height: 2),
                Text(
                  'Último acesso ${rotuloDia(sessao.ultimoUsoEm).toLowerCase()}'
                  ' às ${formatarDataHora(sessao.ultimoUsoEm).substring(11)}',
                  style: tema.bodySmall,
                ),
              ],
            ),
          ),
          if (_encerrando)
            const Padding(
              padding: EdgeInsets.all(12),
              child: SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            )
          else
            TextButton(
              style: TextButton.styleFrom(foregroundColor: VertexColors.erro),
              onPressed: _encerrar,
              child: const Text('Encerrar'),
            ),
        ],
      ),
    );
  }
}
