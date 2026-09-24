import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/formatadores.dart';
import '../../models/conta_pagar.dart';
import '../../theme/vertex_colors.dart';
import 'escolher_anexo.dart';
import 'financeiro_provider.dart';

/// Tela dedicada do comprovante de pagamento de uma despesa -- ver os
/// dados de como foi pago, abrir o arquivo em si, ou trocar por um
/// novo (sem precisar reabrir o formulario de pagamento inteiro).
class ComprovanteScreen extends ConsumerStatefulWidget {
  const ComprovanteScreen({super.key, required this.conta});

  final ContaPagar conta;

  @override
  ConsumerState<ComprovanteScreen> createState() => _ComprovanteScreenState();
}

class _ComprovanteScreenState extends ConsumerState<ComprovanteScreen> {
  bool _carregando = false;

  Future<void> _abrir() async {
    setState(() => _carregando = true);

    final erro = await ref
        .read(financeiroActionsProvider)
        .abrirComprovantePagamento(widget.conta);

    if (!mounted) return;
    setState(() => _carregando = false);

    if (erro != null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(erro)));
    }
  }

  Future<void> _trocar() async {
    final anexo = await escolherAnexoComprovante(context);
    if (anexo == null || !mounted) return;

    setState(() => _carregando = true);

    final erro = await ref
        .read(financeiroActionsProvider)
        .trocarComprovante(widget.conta.id, anexo);

    if (!mounted) return;
    setState(() => _carregando = false);

    if (erro != null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(erro)));
      return;
    }

    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('Comprovante atualizado.')));
    Navigator.of(context).pop(true);
  }

  @override
  Widget build(BuildContext context) {
    final conta = widget.conta;

    return Scaffold(
      appBar: AppBar(title: const Text('Comprovante')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: VertexColors.sucessoClaro,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                  color: VertexColors.secundaria.withValues(alpha: 0.3),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        Icons.check_circle,
                        color: VertexColors.secundaria,
                        size: 22,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        'Pago em ${conta.dataPagamento != null ? formatarData(conta.dataPagamento!) : '—'}',
                        style: TextStyle(
                          fontWeight: FontWeight.w700,
                          color: VertexColors.secundaria,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    conta.descricao ?? 'Despesa',
                    style: TextStyle(
                      fontSize: 13,
                      color: VertexColors.textoSecundario,
                    ),
                  ),
                  Text(
                    formatarMoeda(conta.valor),
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            _LinhaInfo(
              'Forma de pagamento',
              conta.formaPagamento != null
                  ? formatarFormaPagamento(conta.formaPagamento)
                  : '—',
            ),
            _LinhaInfo('Banco', conta.bancoPagamento ?? '—'),
            _LinhaInfo('Número da transação', conta.numeroTransacao ?? '—'),
            _LinhaInfo(
              'Arquivo',
              conta.comprovantePagamentoNome ?? 'Nenhum anexado',
            ),
            const SizedBox(height: 28),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: conta.temComprovantePagamento && !_carregando
                    ? _abrir
                    : null,
                icon: const Icon(Icons.open_in_new, size: 18),
                label: const Text('Abrir / baixar comprovante'),
              ),
            ),
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: _carregando ? null : _trocar,
                icon: _carregando
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.sync, size: 18),
                label: const Text('Trocar comprovante'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LinhaInfo extends StatelessWidget {
  const _LinhaInfo(this.rotulo, this.valor);

  final String rotulo;
  final String valor;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 172,
            child: Text(
              rotulo,
              style: TextStyle(
                fontSize: 13,
                color: VertexColors.textoSecundario,
              ),
            ),
          ),
          Expanded(
            child: Text(
              valor,
              style: const TextStyle(
                fontSize: 13.5,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
