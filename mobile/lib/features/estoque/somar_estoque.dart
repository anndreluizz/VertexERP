import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';
import '../../core/providers.dart';
import 'estoque_provider.dart';

/// Pergunta a quantidade e lanca ENTRADA de um produto que ja existe
/// (POST /estoque/movimentos, exige estoque.ajustar no backend). Usado
/// pela lista do Estoque (toque no produto) e pelo cadastro (codigo
/// que ja existe).
Future<void> somarAoEstoque(
  BuildContext context,
  WidgetRef ref, {
  required int id,
  required String nome,
  required String codigo,
  required num estoque,
  required String titulo,
  required String motivo,
}) async {
  final quantidade = await showDialog<int>(
    context: context,
    builder: (_) => _SomarEstoqueDialog(
      titulo: titulo,
      texto:
          '$nome (código $codigo, estoque atual $estoque).\n\n'
          'Quantas unidades adicionar ao estoque?',
    ),
  );
  if (quantidade == null || !context.mounted) return;

  final mensageiro = ScaffoldMessenger.of(context);
  final lojaId = ref.read(lojaFiltroProvider);
  try {
    await ref
        .read(apiClientProvider)
        .dio
        .post(
          '/estoque/movimentos',
          queryParameters: lojaId != null ? {'loja_id': lojaId} : null,
          data: {
            'produto_id': id,
            'tipo': 'ENTRADA',
            'quantidade': quantidade,
            'motivo': motivo,
          },
        );
    ref.invalidate(produtosProvider);
    mensageiro.showSnackBar(
      SnackBar(
        content: Text('+$quantidade em $nome (agora ${estoque + quantidade}).'),
      ),
    );
  } catch (e) {
    mensageiro.showSnackBar(
      SnackBar(
        content: Text(
          mensagemDeErro(e, fallback: 'Não foi possível adicionar ao estoque.'),
        ),
      ),
    );
  }
}

class _SomarEstoqueDialog extends StatefulWidget {
  const _SomarEstoqueDialog({required this.titulo, required this.texto});

  final String titulo;
  final String texto;

  @override
  State<_SomarEstoqueDialog> createState() => _SomarEstoqueDialogState();
}

class _SomarEstoqueDialogState extends State<_SomarEstoqueDialog> {
  final _quantidade = TextEditingController(text: '1');

  @override
  void dispose() {
    _quantidade.dispose();
    super.dispose();
  }

  void _confirmar() {
    final n = int.tryParse(_quantidade.text.trim());
    if (n != null && n > 0) Navigator.of(context).pop(n);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.titulo),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(widget.texto),
          const SizedBox(height: 12),
          TextField(
            controller: _quantidade,
            autofocus: true,
            keyboardType: TextInputType.number,
            onSubmitted: (_) => _confirmar(),
            decoration: const InputDecoration(border: OutlineInputBorder()),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancelar'),
        ),
        FilledButton(onPressed: _confirmar, child: const Text('Adicionar')),
      ],
    );
  }
}
