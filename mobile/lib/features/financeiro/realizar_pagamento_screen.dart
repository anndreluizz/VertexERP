import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../models/conta_pagar.dart';
import '../../theme/vertex_colors.dart';
import 'escolher_anexo.dart';
import 'financeiro_provider.dart';

/// Formulario completo de pagamento -- o momento mais sensivel do app:
/// confirmar que um pagamento de verdade saiu da conta da loja. Troca
/// o "um toque e pronto" por forma de pagamento, banco, numero da
/// transacao, observacoes e o comprovante em si.
class RealizarPagamentoScreen extends ConsumerStatefulWidget {
  const RealizarPagamentoScreen({super.key, required this.conta});

  final ContaPagar conta;

  @override
  ConsumerState<RealizarPagamentoScreen> createState() =>
      _RealizarPagamentoScreenState();
}

const _formasPagamento = [
  ('PIX', Icons.pix_outlined),
  ('TRANSFERENCIA', Icons.swap_horiz),
  ('DINHEIRO', Icons.payments_outlined),
  ('CARTAO', Icons.credit_card_outlined),
  ('BOLETO', Icons.description_outlined),
];

class _RealizarPagamentoScreenState
    extends ConsumerState<RealizarPagamentoScreen> {
  String _forma = 'PIX';
  final _bancoController = TextEditingController();
  final _transacaoController = TextEditingController();
  final _observacoesController = TextEditingController();
  AnexoEscolhido? _anexo;
  bool _enviando = false;

  @override
  void dispose() {
    _bancoController.dispose();
    _transacaoController.dispose();
    _observacoesController.dispose();
    super.dispose();
  }

  Future<void> _escolherAnexo() async {
    final anexo = await escolherAnexoComprovante(context);
    if (anexo == null || !mounted) return;
    setState(() => _anexo = anexo);
  }

  Future<void> _confirmar() async {
    setState(() => _enviando = true);

    final observacoes = _observacoesController.text.trim();
    String? erro;

    if (observacoes.isNotEmpty) {
      final atual = widget.conta.observacao?.trim() ?? '';
      final nota = 'Pago via ${formatarFormaPagamento(_forma)}. $observacoes';
      erro = await ref
          .read(financeiroActionsProvider)
          .atualizarObservacao(
            widget.conta.id,
            atual.isEmpty ? nota : '$atual\n$nota',
          );
    }

    erro ??= await ref
        .read(financeiroActionsProvider)
        .pagarConta(
          widget.conta.id,
          formaPagamento: _forma,
          banco: _bancoController.text.trim(),
          numeroTransacao: _transacaoController.text.trim(),
          comprovante: _anexo,
        );

    if (!mounted) return;
    setState(() => _enviando = false);

    if (erro != null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(erro)));
      return;
    }

    Navigator.of(context).pop(true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Realizar Pagamento')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: VertexColors.primariaClara,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    widget.conta.descricao ?? 'Despesa',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    formatarMoeda(widget.conta.valor),
                    style: Theme.of(
                      context,
                    ).textTheme.headlineSmall?.copyWith(
                      color: VertexColors.primaria,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  Text(
                    'Vencimento: ${formatarData(widget.conta.dataVencimento)}',
                    style: TextStyle(
                      fontSize: 12,
                      color: VertexColors.textoSecundario,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            const Text(
              'Forma de pagamento',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final (valor, icone) in _formasPagamento)
                  ChoiceChip(
                    label: Text(formatarFormaPagamento(valor)),
                    avatar: Icon(icone, size: 16),
                    selected: _forma == valor,
                    onSelected: (_) => setState(() => _forma = valor),
                  ),
              ],
            ),
            const SizedBox(height: 20),
            TextField(
              controller: _bancoController,
              decoration: const InputDecoration(
                labelText: 'Banco utilizado',
                hintText: 'Ex.: Itaú, Nubank...',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 14),
            TextField(
              controller: _transacaoController,
              decoration: const InputDecoration(
                labelText: 'Número da transação',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 14),
            TextField(
              controller: _observacoesController,
              maxLines: 3,
              decoration: const InputDecoration(
                labelText: 'Observações',
                alignLabelWithHint: true,
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 20),
            const Text(
              'Comprovante',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 10),
            InkWell(
              onTap: _escolherAnexo,
              borderRadius: BorderRadius.circular(10),
              child: Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  border: Border.all(
                    color: VertexColors.borda,
                    style: BorderStyle.solid,
                  ),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  children: [
                    Icon(
                      _anexo == null
                          ? Icons.attach_file
                          : Icons.check_circle_outline,
                      color: _anexo == null
                          ? VertexColors.textoSecundario
                          : VertexColors.secundaria,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        _anexo?.nome ??
                            'Fotografar ou escolher o comprovante',
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: 13,
                          color: _anexo == null
                              ? VertexColors.textoSecundario
                              : VertexColors.texto,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 28),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _enviando ? null : _confirmar,
                style: FilledButton.styleFrom(
                  backgroundColor: VertexColors.secundaria,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                child: _enviando
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Text('Confirmar pagamento'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
