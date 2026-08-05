import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../models/sessao.dart';
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
              padding: const EdgeInsets.all(16),
              children: [
                Text(
                  'Aparelhos com sessão aberta na sua conta. Encerre '
                  'qualquer uma remotamente se não reconhecer ou não '
                  'usar mais um deles.',
                  style: TextStyle(
                    fontSize: 12.5,
                    color: VertexColors.textoSecundario,
                  ),
                ),
                const SizedBox(height: 16),
                for (final sessao in sessoes) ...[
                  _CartaoSessao(sessao: sessao),
                  const SizedBox(height: 10),
                ],
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

    return Card(
      margin: EdgeInsets.zero,
      child: ListTile(
        leading: Container(
          width: 38,
          height: 38,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: VertexColors.primariaClara,
            borderRadius: BorderRadius.circular(11),
          ),
          child: const Icon(
            Icons.smartphone,
            size: 18,
            color: VertexColors.primaria,
          ),
        ),
        title: Text(sessao.dispositivo ?? 'Aparelho desconhecido'),
        subtitle: Text(
          'Último acesso: ${formatarDataHora(sessao.ultimoUsoEm)}',
          style: const TextStyle(fontSize: 12),
        ),
        trailing: _encerrando
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : IconButton(
                icon: const Icon(Icons.logout, color: VertexColors.erro),
                tooltip: 'Encerrar sessão',
                onPressed: _encerrar,
              ),
      ),
    );
  }
}
