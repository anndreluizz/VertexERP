import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../models/solicitacao_aprovacao.dart';
import '../../theme/vertex_colors.dart';
import 'aprovacoes_provider.dart';

class AprovacoesScreen extends ConsumerWidget {
  const AprovacoesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pendentesAsync = ref.watch(aprovacoesPendentesProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Aprovações')),
      body: RefreshIndicator(
        onRefresh: () => ref.refresh(aprovacoesPendentesProvider.future),
        child: pendentesAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (erro, _) => ListView(
            children: const [
              SizedBox(height: 80),
              Center(
                child: Text('Não foi possível carregar as aprovações.'),
              ),
            ],
          ),
          data: (pendentes) {
            if (pendentes.isEmpty) {
              return ListView(
                children: const [
                  SizedBox(height: 80),
                  Center(
                    child: Icon(
                      Icons.check_circle_outline,
                      size: 36,
                      color: VertexColors.textoTerciario,
                    ),
                  ),
                  SizedBox(height: 12),
                  Center(child: Text('Nenhuma aprovação pendente.')),
                ],
              );
            }

            return ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: pendentes.length,
              separatorBuilder: (_, _) => const SizedBox(height: 10),
              itemBuilder: (context, indice) =>
                  _CartaoAprovacao(solicitacao: pendentes[indice]),
            );
          },
        ),
      ),
    );
  }
}

class _CartaoAprovacao extends ConsumerStatefulWidget {
  const _CartaoAprovacao({required this.solicitacao});

  final SolicitacaoAprovacao solicitacao;

  @override
  ConsumerState<_CartaoAprovacao> createState() => _CartaoAprovacaoState();
}

class _CartaoAprovacaoState extends ConsumerState<_CartaoAprovacao> {
  bool _processando = false;

  Future<void> _responder(bool aprovar) async {
    setState(() => _processando = true);

    final acoes = ref.read(aprovacoesActionsProvider);

    final erro = aprovar
        ? await acoes.aprovar(widget.solicitacao.id)
        : await acoes.rejeitar(widget.solicitacao.id);

    if (!mounted) return;

    setState(() => _processando = false);

    if (erro != null) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(erro)));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: VertexColors.alertaClaro,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(
                    Icons.help_outline,
                    size: 18,
                    color: VertexColors.alerta,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    formatarDataHora(widget.solicitacao.criadoEm),
                    style: TextStyle(
                      fontSize: 11.5,
                      color: VertexColors.textoTerciario,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(widget.solicitacao.descricao),
            const SizedBox(height: 14),
            if (_processando)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(8),
                  child: SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                ),
              )
            else
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => _responder(false),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: VertexColors.erro,
                        side: const BorderSide(color: VertexColors.erro),
                      ),
                      child: const Text('Rejeitar'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () => _responder(true),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: VertexColors.secundaria,
                      ),
                      child: const Text('Aprovar'),
                    ),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}
