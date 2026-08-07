import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/formatadores.dart';
import '../../core/providers.dart';
import '../../models/cliente.dart';
import '../../models/movimento_fiado.dart';
import '../../theme/vertex_colors.dart';
import 'clientes_provider.dart';

class ClienteDetalheScreen extends ConsumerWidget {
  const ClienteDetalheScreen({super.key, required this.clienteId});

  final int clienteId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final clienteAsync = ref.watch(clienteProvider(clienteId));

    return Scaffold(
      appBar: AppBar(title: const Text('Ficha do cliente')),
      body: clienteAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (erro, _) =>
            const Center(child: Text('Não foi possível carregar o cliente.')),
        data: (cliente) => _Ficha(cliente: cliente),
      ),
    );
  }
}

class _Ficha extends ConsumerWidget {
  const _Ficha({required this.cliente});

  final Cliente cliente;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final saldoAsync = ref.watch(saldoFiadoProvider(cliente.id));
    final historicoAsync = ref.watch(historicoFiadoProvider(cliente.id));
    final estatisticasAsync = ref.watch(estatisticasClienteProvider(cliente.id));

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(saldoFiadoProvider(cliente.id));
        ref.invalidate(historicoFiadoProvider(cliente.id));
        await ref.read(historicoFiadoProvider(cliente.id).future);
      },
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      CircleAvatar(
                        radius: 26,
                        backgroundColor: VertexColors.primariaClara,
                        child: Text(
                          cliente.nome.isEmpty
                              ? '?'
                              : cliente.nome[0].toUpperCase(),
                          style: const TextStyle(
                            color: VertexColors.primaria,
                            fontWeight: FontWeight.w700,
                            fontSize: 18,
                          ),
                        ),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              cliente.nome,
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                            Text(
                              'Cliente desde ${formatarData(cliente.criadoEm)}',
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
                  const Divider(height: 28),
                  if (cliente.telefone != null)
                    _linhaContato(
                      Icons.phone_outlined,
                      cliente.telefone!,
                    ),
                  if (cliente.email != null)
                    _linhaContato(Icons.mail_outline, cliente.email!),
                  if (cliente.enderecoCompleto.isNotEmpty)
                    _linhaContato(
                      Icons.location_on_outlined,
                      cliente.enderecoCompleto,
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () {
                    ref.read(abaSelecionadaProvider.notifier).state = 1;
                    Navigator.of(context).pop();
                  },
                  icon: const Icon(Icons.point_of_sale_outlined, size: 17),
                  label: const Text('Nova venda'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => _abrirReceber(context, ref),
                  icon: const Icon(Icons.call_received, size: 17),
                  label: const Text('Receber'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _botaoMenuWhatsapp(context, ref),
              ),
            ],
          ),
          const SizedBox(height: 14),
          estatisticasAsync.when(
            loading: () => const SizedBox.shrink(),
            error: (erro, _) => const SizedBox.shrink(),
            data: (estatisticas) => Row(
              children: [
                Expanded(
                  child: _CartaoValor(
                    rotulo: 'Última compra',
                    valor: estatisticas.ultimaCompra != null
                        ? formatarData(estatisticas.ultimaCompra!)
                        : '—',
                    cor: VertexColors.texto,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _CartaoValor(
                    rotulo: 'Total comprado',
                    valor: formatarMoeda(estatisticas.totalComprado),
                    cor: VertexColors.texto,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _CartaoValor(
                    rotulo: 'Qtd. compras',
                    valor: '${estatisticas.qtdCompras}',
                    cor: VertexColors.texto,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _CartaoValor(
                  rotulo: 'Limite de crédito',
                  valor: cliente.limiteCredito != null
                      ? formatarMoeda(cliente.limiteCredito!)
                      : '—',
                  cor: VertexColors.primaria,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: saldoAsync.when(
                  loading: () => const _CartaoValor(
                    rotulo: 'Saldo devedor',
                    valor: '...',
                    cor: VertexColors.alerta,
                  ),
                  error: (erro, _) => const _CartaoValor(
                    rotulo: 'Saldo devedor',
                    valor: '—',
                    cor: VertexColors.alerta,
                  ),
                  data: (saldo) => _CartaoValor(
                    rotulo: 'Saldo devedor',
                    valor: formatarMoeda(saldo),
                    cor: saldo > 0
                        ? VertexColors.erro
                        : VertexColors.secundaria,
                    destaque:
                        cliente.limiteCredito != null &&
                        saldo > cliente.limiteCredito!,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Text(
            'Histórico financeiro',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          historicoAsync.when(
            loading: () => const Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: CircularProgressIndicator()),
            ),
            error: (erro, _) => const Padding(
              padding: EdgeInsets.all(16),
              child: Text('Não foi possível carregar o histórico.'),
            ),
            data: (movimentos) {
              if (movimentos.isEmpty) {
                return const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('Nenhuma movimentação registrada.'),
                );
              }

              return Card(
                child: Column(
                  children: [
                    for (final movimento in movimentos)
                      _linhaMovimento(context, movimento),
                  ],
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  /// Botão "WhatsApp" virou um menu com as mesmas ações do Desktop
  /// (extrato completo, cobrança, saldo devedor, haver, cadastro) --
  /// todas via texto livre, mesmo endpoint POST /clientes/{id}/whatsapp.
  Widget _botaoMenuWhatsapp(BuildContext context, WidgetRef ref) {
    return PopupMenuButton<_AcaoWhatsapp>(
      tooltip: 'WhatsApp',
      enabled: cliente.telefone != null,
      onSelected: (acao) => _executarAcaoWhatsapp(context, ref, acao),
      itemBuilder: (context) => const [
        PopupMenuItem(
          value: _AcaoWhatsapp.extrato,
          child: Text('Enviar Extrato Completo'),
        ),
        PopupMenuItem(
          value: _AcaoWhatsapp.cobranca,
          child: Text('Enviar Cobrança'),
        ),
        PopupMenuItem(
          value: _AcaoWhatsapp.saldo,
          child: Text('Enviar Saldo Devedor'),
        ),
        PopupMenuItem(
          value: _AcaoWhatsapp.haver,
          child: Text('Enviar Haver'),
        ),
        PopupMenuItem(
          value: _AcaoWhatsapp.cadastro,
          child: Text('Enviar Cadastro do Cliente'),
        ),
      ],
      child: IgnorePointer(
        child: OutlinedButton.icon(
          onPressed: cliente.telefone == null ? null : () {},
          icon: const Icon(Icons.chat_outlined, size: 17),
          label: const Text('WhatsApp'),
        ),
      ),
    );
  }

  Future<void> _executarAcaoWhatsapp(
    BuildContext context,
    WidgetRef ref,
    _AcaoWhatsapp acao,
  ) async {
    final saldo = await ref.read(saldoFiadoProvider(cliente.id).future);
    final historico = await ref.read(historicoFiadoProvider(cliente.id).future);

    if (!context.mounted) return;

    // historicoFiadoProvider ordena mais-novo primeiro; pra somar saldo
    // corrido (igual o Desktop) precisamos da ordem cronologica.
    final cronologico = [...historico]
      ..sort((a, b) => a.data.compareTo(b.data));

    String? texto;

    switch (acao) {
      case _AcaoWhatsapp.extrato:
        texto = _textoExtrato(saldo, cronologico);
        break;
      case _AcaoWhatsapp.cobranca:
        if (saldo <= 0) {
          _mostrarSnack(context, 'Este cliente não tem saldo devedor.');
          return;
        }
        texto = _textoCobranca(saldo);
        break;
      case _AcaoWhatsapp.saldo:
        texto = _textoSaldoDevedor(saldo);
        break;
      case _AcaoWhatsapp.haver:
        final haveres = cronologico
            .where((m) => m.tipo == 'HAVER')
            .toList();
        if (haveres.isEmpty) {
          _mostrarSnack(
            context,
            'Este cliente ainda não tem nenhum crédito (Haver) lançado.',
          );
          return;
        }
        texto = _textoHaver(haveres.last, cronologico);
        break;
      case _AcaoWhatsapp.cadastro:
        texto = _textoCadastro(saldo);
        break;
    }

    if (!context.mounted) return;

    final enviado = await ref
        .read(clientesActionsProvider)
        .enviarWhatsapp(cliente.id, texto);

    if (!context.mounted) return;

    if (enviado) {
      _mostrarSnack(context, 'Mensagem enviada pelo WhatsApp com sucesso.');
      return;
    }

    // fallback: abre o WhatsApp com a mensagem ja pronta (integracao
    // Z-API desligada ou envio automatico falhou).
    await _abrirWhatsApp(context, cliente.telefone!, texto: texto);
  }

  String _cabecalho(String titulo) => '*$titulo*';

  String _textoExtrato(double saldo, List<MovimentoFiado> cronologico) {
    var saldoCorrido = 0.0;
    final linhas = <String>[];
    var totalComprado = 0.0;
    var totalPago = 0.0;

    for (final mov in cronologico) {
      final compra = mov.tipo == 'COMPRA';
      saldoCorrido += compra ? mov.valor : -mov.valor;

      if (compra) {
        totalComprado += mov.valor;
      } else if (mov.tipo == 'PAGAMENTO') {
        totalPago += mov.valor;
      }

      final rotulo = switch (mov.tipo) {
        'COMPRA' => '🛒 Compra',
        'PAGAMENTO' => '💵 Pagamento',
        'HAVER' => '💰 Haver',
        _ => mov.tipo,
      };
      final sinal = compra ? '+' : '-';

      linhas.add(
        '${formatarDataHora(mov.data)} | $rotulo | '
        '${mov.descricao ?? "—"} | $sinal ${formatarMoeda(mov.valor)} | '
        'Saldo: ${formatarMoeda(saldoCorrido)}',
      );
    }

    final movimentacoes = linhas.isEmpty
        ? 'Nenhuma movimentação registrada.'
        : linhas.join('\n');

    return '${_cabecalho('EXTRATO DO CLIENTE')}\n\n'
        'Cliente: ${cliente.nome}\n'
        'Telefone: ${cliente.telefone ?? "—"}\n'
        'Cliente desde: ${formatarData(cliente.criadoEm)}\n'
        'Saldo Atual: ${formatarMoeda(saldo)}\n\n'
        '*MOVIMENTAÇÕES*\n'
        '$movimentacoes\n\n'
        'Total Comprado: ${formatarMoeda(totalComprado)}\n'
        'Total Pago: ${formatarMoeda(totalPago)}\n'
        'Saldo Devedor: ${formatarMoeda(saldo)}\n\n'
        'Muito obrigado pela preferência!';
  }

  String _textoCobranca(double saldo) {
    return '${_cabecalho('COBRANÇA')}\n\n'
        'Olá, ${cliente.nome}! 👋\n\n'
        'Passando pra lembrar que você tem um saldo em aberto no valor '
        'de ${formatarMoeda(saldo)}.\n\n'
        'Qualquer dúvida, é só chamar. Obrigado!';
  }

  String _textoSaldoDevedor(double saldo) {
    return '${_cabecalho('SALDO DEVEDOR')}\n\n'
        'Olá, ${cliente.nome}!\n'
        'Seu saldo devedor atual é de ${formatarMoeda(saldo)}.';
  }

  String _textoHaver(MovimentoFiado haver, List<MovimentoFiado> cronologico) {
    var saldoCorrido = 0.0;
    for (final mov in cronologico) {
      final compra = mov.tipo == 'COMPRA';
      saldoCorrido += compra ? mov.valor : -mov.valor;
      if (identical(mov, haver)) break;
    }

    return '${_cabecalho('CRÉDITO (HAVER)')}\n\n'
        'Olá, ${cliente.nome}!\n'
        'Você recebeu um crédito de ${formatarMoeda(haver.valor)} em '
        '${formatarDataHora(haver.data)}.\n'
        'Motivo: ${haver.descricao ?? "—"}\n\n'
        'Seu saldo devedor atualizado é de ${formatarMoeda(saldoCorrido)}.';
  }

  String _textoCadastro(double saldo) {
    final partes = <String>[
      _cabecalho('CADASTRO DO CLIENTE'),
      '',
      'Nome: ${cliente.nome}',
    ];

    if (cliente.cpfCnpj != null) partes.add('CPF/CNPJ: ${cliente.cpfCnpj}');
    if (cliente.telefone != null) partes.add('Telefone: ${cliente.telefone}');
    if (cliente.email != null) partes.add('E-mail: ${cliente.email}');
    if (cliente.enderecoCompleto.isNotEmpty) {
      partes.add('Endereço: ${cliente.enderecoCompleto}');
    }

    partes.add('Cliente desde: ${formatarData(cliente.criadoEm)}');
    partes.add('Saldo Atual: ${formatarMoeda(saldo)}');
    partes.add('');
    partes.add('Muito obrigado pela preferência!');

    return partes.join('\n');
  }

  void _mostrarSnack(BuildContext context, String mensagem) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(mensagem)),
    );
  }

  Future<void> _abrirWhatsApp(
    BuildContext context,
    String telefone, {
    String? texto,
  }) async {
    final numero = telefone.replaceAll(RegExp(r'[^0-9]'), '');
    final query = texto != null ? '?text=${Uri.encodeComponent(texto)}' : '';
    final uri = Uri.parse('https://wa.me/55$numero$query');

    final abriu = await launchUrl(uri, mode: LaunchMode.externalApplication);

    if (!abriu && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Não foi possível abrir o WhatsApp.')),
      );
    }
  }

  Future<void> _abrirReceber(BuildContext context, WidgetRef ref) async {
    final controller = TextEditingController();

    final valor = await showDialog<double>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Receber de ${cliente.nome}'),
        content: TextField(
          controller: controller,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          autofocus: true,
          decoration: const InputDecoration(
            labelText: 'Valor recebido',
            prefixText: 'R\$ ',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () {
              final digitado = double.tryParse(
                controller.text.replaceAll(',', '.'),
              );
              Navigator.of(context).pop(digitado);
            },
            child: const Text('Registrar'),
          ),
        ],
      ),
    );

    if (valor == null || valor <= 0 || !context.mounted) return;

    final erro = await ref
        .read(clientesActionsProvider)
        .receberPagamento(cliente.id, valor);

    if (!context.mounted) return;

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(erro ?? 'Recebimento registrado com sucesso.'),
      ),
    );
  }

  Widget _linhaContato(IconData icone, String texto) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(icone, size: 17, color: VertexColors.textoTerciario),
          const SizedBox(width: 10),
          Expanded(child: Text(texto)),
        ],
      ),
    );
  }

  Widget _linhaMovimento(BuildContext context, MovimentoFiado movimento) {
    final compra = movimento.tipo == 'COMPRA';

    final IconData iconeMovimento;
    final Color cor;
    final String descricaoPadrao;

    if (compra) {
      iconeMovimento = Icons.arrow_upward;
      cor = VertexColors.erro;
      descricaoPadrao = 'Compra a prazo';
    } else if (movimento.tipo == 'HAVER') {
      iconeMovimento = Icons.card_giftcard;
      cor = VertexColors.alerta;
      descricaoPadrao = 'Crédito (Haver)';
    } else {
      iconeMovimento = Icons.arrow_downward;
      cor = VertexColors.secundaria;
      descricaoPadrao = 'Pagamento';
    }

    return Padding(
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          Icon(iconeMovimento, size: 17, color: cor),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  movimento.descricao ?? descricaoPadrao,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                Text(
                  formatarData(movimento.data),
                  style: TextStyle(
                    fontSize: 12,
                    color: VertexColors.textoSecundario,
                  ),
                ),
              ],
            ),
          ),
          Text(
            '${compra ? '+' : '-'} ${formatarMoeda(movimento.valor)}',
            style: TextStyle(
              fontWeight: FontWeight.w700,
              color: cor,
            ),
          ),
        ],
      ),
    );
  }
}

enum _AcaoWhatsapp { extrato, cobranca, saldo, haver, cadastro }

class _CartaoValor extends StatelessWidget {
  const _CartaoValor({
    required this.rotulo,
    required this.valor,
    required this.cor,
    this.destaque = false,
  });

  final String rotulo;
  final String valor;
  final Color cor;
  final bool destaque;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      color: destaque ? VertexColors.erroClaro : null,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              rotulo,
              style: TextStyle(
                fontSize: 11.5,
                color: VertexColors.textoSecundario,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              valor,
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w800,
                color: cor,
              ),
            ),
            if (destaque) ...[
              const SizedBox(height: 2),
              const Text(
                'Acima do limite',
                style: TextStyle(fontSize: 10.5, color: VertexColors.erro),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
