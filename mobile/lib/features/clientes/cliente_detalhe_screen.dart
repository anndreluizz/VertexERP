import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/cliente_analise.dart';
import '../../core/formatadores.dart';
import '../../models/cliente.dart';
import '../../models/movimento_fiado.dart';
import '../../theme/componentes.dart';
import '../../theme/lista_agrupada.dart';
import '../../theme/skeleton.dart';
import '../../theme/vertex_colors.dart';
import '../../theme/vertex_theme.dart';
import 'clientes_provider.dart';

class ClienteDetalheScreen extends ConsumerWidget {
  const ClienteDetalheScreen({super.key, required this.clienteId});

  final int clienteId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final clienteAsync = ref.watch(clienteProvider(clienteId));

    return clienteAsync.when(
      loading: () => Scaffold(
        appBar: AppBar(),
        body: const Center(child: CircularProgressIndicator()),
      ),
      error: (erro, _) => Scaffold(
        appBar: AppBar(),
        body: const Center(child: Text('Não foi possível carregar o cliente.')),
      ),
      data: (cliente) => _Ficha(cliente: cliente),
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
    final analise = historicoAsync.hasValue
        ? analisarCliente(historicoAsync.value!)
        : null;
    final saldo = saldoAsync.valueOrNull ?? analise?.saldoDevedor;
    final (fundoStatus, corStatus, _) = coresStatusCliente(
      analise?.status ?? StatusCliente.quitado,
    );

    return Scaffold(
      appBar: AppBar(
        actions: [
          if (cliente.telefone != null)
            IconButton(
              tooltip: 'Ligar',
              icon: const Icon(Icons.call_outlined),
              onPressed: () => launchUrl(
                Uri.parse(
                  'tel:${cliente.telefone!.replaceAll(RegExp(r'[^0-9+]'), '')}',
                ),
              ),
            ),
          const SizedBox(width: 8),
        ],
      ),
      bottomNavigationBar: SafeArea(
        child: Container(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
          decoration: BoxDecoration(
            color: VertexColors.card,
            border: Border(top: BorderSide(color: VertexColors.borda)),
          ),
          child: Row(
            children: [
              Expanded(child: _botaoMenuWhatsapp(context, ref)),
              const SizedBox(width: 10),
              Expanded(
                child: FilledButton.icon(
                  style: FilledButton.styleFrom(
                    minimumSize: const Size(64, 52),
                  ),
                  onPressed: () => _abrirReceber(context, ref, saldo ?? 0),
                  icon: const Icon(Icons.payments_outlined, size: 20),
                  label: const Text('Receber'),
                ),
              ),
            ],
          ),
        ),
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(saldoFiadoProvider(cliente.id));
          ref.invalidate(historicoFiadoProvider(cliente.id));
          await ref.read(historicoFiadoProvider(cliente.id).future);
        },
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
          children: [
            _Cabecalho(
              cliente: cliente,
              status: analise?.status,
              fundo: fundoStatus,
              cor: corStatus,
            ),
            const SizedBox(height: 16),
            saldoAsync.isLoading && analise == null
                ? const SkeletonBox(height: 132, borderRadius: 20)
                : _PainelSaldo(saldo: saldo, limite: cliente.limiteCredito),
            const SizedBox(height: 12),
            if (analise != null) _Indicadores(analise: analise),
            const SizedBox(height: 22),
            const TituloSecao('Histórico'),
            historicoAsync.when(
              loading: () => const SkeletonListCard(),
              error: (erro, _) => const Padding(
                padding: EdgeInsets.all(16),
                child: Text('Não foi possível carregar o histórico.'),
              ),
              data: (movimentos) {
                if (movimentos.isEmpty) {
                  return Padding(
                    padding: const EdgeInsets.all(16),
                    child: Text(
                      'Nenhuma movimentação registrada.',
                      style: TextStyle(color: VertexColors.textoSecundario),
                    ),
                  );
                }

                return ListaAgrupada(
                  recuo: 62,
                  linhas: [
                    for (final movimento in movimentos)
                      _linhaMovimento(context, movimento),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  /// "Cobrar" abre o menu com as mesmas mensagens do Desktop (extrato,
  /// cobranca, saldo, haver, cadastro) -- todas via texto livre, mesmo
  /// endpoint POST /clientes/{id}/whatsapp.
  Widget _botaoMenuWhatsapp(BuildContext context, WidgetRef ref) {
    final temTelefone = cliente.telefone != null;

    return PopupMenuButton<_AcaoWhatsapp>(
      tooltip: temTelefone ? 'Mensagens pelo WhatsApp' : 'Cliente sem telefone',
      enabled: temTelefone,
      position: PopupMenuPosition.over,
      onSelected: (acao) => _executarAcaoWhatsapp(context, ref, acao),
      itemBuilder: (context) => const [
        PopupMenuItem(
          value: _AcaoWhatsapp.cobranca,
          child: Text('Enviar cobrança'),
        ),
        PopupMenuItem(
          value: _AcaoWhatsapp.saldo,
          child: Text('Enviar saldo devedor'),
        ),
        PopupMenuItem(
          value: _AcaoWhatsapp.extrato,
          child: Text('Enviar extrato completo'),
        ),
        PopupMenuItem(value: _AcaoWhatsapp.haver, child: Text('Enviar haver')),
        PopupMenuItem(
          value: _AcaoWhatsapp.cadastro,
          child: Text('Enviar cadastro do cliente'),
        ),
      ],
      child: IgnorePointer(
        child: OutlinedButton.icon(
          style: OutlinedButton.styleFrom(minimumSize: const Size(64, 52)),
          onPressed: temTelefone ? () {} : null,
          icon: Icon(
            Icons.chat_outlined,
            size: 20,
            color: temTelefone ? VertexColors.secundaria : null,
          ),
          label: const Text('Cobrar'),
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
        final haveres = cronologico.where((m) => m.tipo == 'HAVER').toList();
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
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(mensagem)));
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

  Future<void> _abrirReceber(
    BuildContext context,
    WidgetRef ref,
    double saldo,
  ) async {
    final valor = await showModalBottomSheet<double>(
      context: context,
      isScrollControlled: true,
      builder: (context) => _ReceberSheet(nome: cliente.nome, saldo: saldo),
    );

    if (valor == null || valor <= 0 || !context.mounted) return;

    final erro = await ref
        .read(clientesActionsProvider)
        .receberPagamento(cliente.id, valor);

    if (!context.mounted) return;

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          erro ?? 'Recebimento de ${formatarMoeda(valor)} registrado.',
        ),
      ),
    );
  }

  Widget _linhaMovimento(BuildContext context, MovimentoFiado movimento) {
    final compra = movimento.tipo == 'COMPRA';
    final saldoAnterior =
        compra && (movimento.descricao ?? '').toLowerCase() == 'saldo anterior';

    final IconData icone;
    final Color fundo;
    final Color cor;
    final String titulo;

    if (saldoAnterior) {
      icone = Icons.menu_book_outlined;
      fundo = VertexColors.primariaClara;
      cor = VertexColors.escuro ? VertexColors.texto : VertexColors.primaria;
      titulo = 'Saldo anterior';
    } else if (compra) {
      icone = Icons.shopping_cart_outlined;
      fundo = VertexColors.fundo;
      cor = VertexColors.texto;
      titulo = movimento.vendaId != null
          ? 'Compra · Venda #${movimento.vendaId}'
          : (movimento.descricao ?? 'Compra a prazo');
    } else if (movimento.tipo == 'HAVER') {
      icone = Icons.savings_outlined;
      fundo = VertexColors.alertaClaro;
      cor = VertexColors.alertaTexto;
      titulo = movimento.descricao ?? 'Crédito (haver)';
    } else {
      icone = Icons.check_rounded;
      fundo = VertexColors.sucessoClaro;
      cor = VertexColors.sucesso;
      final forma = formatarFormaPagamento(movimento.formaPagamento);
      titulo = forma.isEmpty ? 'Pagamento' : 'Pagamento · $forma';
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: fundo,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icone, size: 18, color: cor),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  titulo,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 14.5,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  formatarDataHora(movimento.data),
                  style: TextStyle(
                    fontSize: 12.5,
                    color: VertexColors.textoSecundario,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          Text(
            '${compra ? '+' : '−'} ${formatarMoeda(movimento.valor)}',
            style: TextStyle(
              fontSize: 14.5,
              fontWeight: FontWeight.w700,
              fontFeatures: tabular,
              color: compra ? VertexColors.texto : VertexColors.sucesso,
            ),
          ),
        ],
      ),
    );
  }
}

enum _AcaoWhatsapp { extrato, cobranca, saldo, haver, cadastro }

class _Cabecalho extends StatelessWidget {
  const _Cabecalho({
    required this.cliente,
    required this.status,
    required this.fundo,
    required this.cor,
  });

  final Cliente cliente;
  final StatusCliente? status;
  final Color fundo;
  final Color cor;

  @override
  Widget build(BuildContext context) {
    final detalhe = [
      cliente.telefone ?? '',
      'cliente desde ${cliente.criadoEm.year}',
    ].where((p) => p.isNotEmpty).join(' · ');

    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 0, 4, 0),
      child: Row(
        children: [
          AvatarIniciais(
            nome: cliente.nome,
            fundo: fundo,
            cor: cor,
            tamanho: 60,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  cliente.nome,
                  style: TextStyle(
                    fontFamily: VertexTheme.fonteDisplay,
                    fontSize: 24,
                    fontWeight: FontWeight.w700,
                    height: 1.15,
                    color: VertexColors.texto,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  detalhe,
                  style: TextStyle(
                    fontSize: 13.5,
                    color: VertexColors.textoSecundario,
                  ),
                ),
                if (status != null) ...[
                  const SizedBox(height: 6),
                  SeloStatusCliente(status!),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Saldo devedor em destaque + quanto do limite ja foi usado -- a
/// pergunta que o dono faz ao abrir a ficha ("quanto ele me deve, e
/// ainda pode comprar fiado?").
class _PainelSaldo extends StatelessWidget {
  const _PainelSaldo({required this.saldo, required this.limite});

  final double? saldo;
  final double? limite;

  @override
  Widget build(BuildContext context) {
    final valor = saldo ?? 0;
    final temLimite = limite != null && limite! > 0;
    final uso = temLimite ? valor / limite! : 0.0;
    final estourou = temLimite && valor > limite!;
    final corBarra = estourou
        ? VertexPaletaEscuraSobreAzul.erro
        : uso > 0.8
        ? VertexPaletaEscuraSobreAzul.alerta
        : VertexPaletaEscuraSobreAzul.ok;
    const textoClaro = Color(0xFFC7D2E3);

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: VertexColors.escuro
            ? VertexColors.primariaClara
            : VertexColors.sidebar,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'SALDO DEVEDOR',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.6,
              color: textoClaro,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            saldo == null ? '—' : formatarMoeda(valor),
            style: const TextStyle(
              fontFamily: VertexTheme.fonteDisplay,
              fontSize: 36,
              fontWeight: FontWeight.w700,
              height: 1,
              color: Colors.white,
              fontFeatures: tabular,
            ),
          ),
          const SizedBox(height: 14),
          if (temLimite) ...[
            BarraProgresso(
              fracao: uso,
              cor: corBarra,
              fundo: const Color(0xFF24406B),
              altura: 8,
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: Text(
                    estourou
                        ? 'Acima do limite!'
                        : '${(uso * 100).round()}% do limite usado',
                    style: TextStyle(
                      fontSize: 13,
                      color: estourou
                          ? VertexPaletaEscuraSobreAzul.erro
                          : textoClaro,
                      fontWeight: estourou ? FontWeight.w700 : null,
                    ),
                  ),
                ),
                Text(
                  'Limite ${formatarMoeda(limite!)}',
                  style: const TextStyle(
                    fontSize: 13,
                    color: textoClaro,
                    fontFeatures: tabular,
                  ),
                ),
              ],
            ),
          ] else
            const Text(
              'Sem limite de crédito definido',
              style: TextStyle(fontSize: 13, color: textoClaro),
            ),
        ],
      ),
    );
  }
}

/// Cores legiveis sobre o cartao azul-marinho do saldo (as do tema sao
/// pensadas pra fundo claro).
class VertexPaletaEscuraSobreAzul {
  static const ok = Color(0xFF3FBFA0);
  static const alerta = Color(0xFFD69A3E);
  static const erro = Color(0xFFFF8A80);
}

class _Indicadores extends StatelessWidget {
  const _Indicadores({required this.analise});

  final AnaliseCliente analise;

  @override
  Widget build(BuildContext context) {
    final atraso = analise.diasEmAtraso;
    final prazo = analise.prazoMedioPagamento;
    final corAtraso = analise.inadimplente
        ? VertexColors.erro
        : (atraso ?? 0) > prazoBomPagadorDias
        ? VertexColors.alertaTexto
        : VertexColors.texto;

    String dias(int? n) => n == null ? '—' : (n == 1 ? '1 dia' : '$n dias');

    return Row(
      children: [
        Expanded(
          child: _Indicador(
            rotulo: 'Compra mais antiga em aberto',
            valor: dias(atraso),
            cor: corAtraso,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _Indicador(rotulo: 'Costuma pagar em', valor: dias(prazo)),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _Indicador(
            rotulo: 'Total comprado no fiado',
            valor: formatarMoeda(analise.totalComprado),
          ),
        ),
      ],
    );
  }
}

class _Indicador extends StatelessWidget {
  const _Indicador({required this.rotulo, required this.valor, this.cor});

  final String rotulo;
  final String valor;
  final Color? cor;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(10, 12, 10, 12),
      decoration: BoxDecoration(
        color: VertexColors.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: VertexColors.borda),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            height: 30,
            child: Text(
              rotulo,
              maxLines: 2,
              style: TextStyle(
                fontSize: 11.5,
                height: 1.3,
                color: VertexColors.textoSecundario,
              ),
            ),
          ),
          const SizedBox(height: 4),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(
              valor,
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w700,
                fontFeatures: tabular,
                color: cor ?? VertexColors.texto,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Folha de recebimento: valor ja sugerido (o saldo todo) e atalhos de
/// valor, pra receber com 2 toques no caso mais comum.
class _ReceberSheet extends StatefulWidget {
  const _ReceberSheet({required this.nome, required this.saldo});

  final String nome;
  final double saldo;

  @override
  State<_ReceberSheet> createState() => _ReceberSheetState();
}

class _ReceberSheetState extends State<_ReceberSheet> {
  late final _controller = TextEditingController(
    text: widget.saldo > 0
        ? widget.saldo.toStringAsFixed(2).replaceAll('.', ',')
        : '',
  );
  String? _erro;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  double? get _valor => double.tryParse(
    _controller.text.trim().replaceAll('.', '').replaceAll(',', '.'),
  );

  void _usar(double v) {
    _controller.text = v.toStringAsFixed(2).replaceAll('.', ',');
    setState(() => _erro = null);
  }

  void _confirmar() {
    final v = _valor;
    if (v == null || v <= 0) {
      setState(() => _erro = 'Digite um valor maior que zero.');
      return;
    }
    if (widget.saldo > 0 && v > widget.saldo + 0.009) {
      setState(
        () => _erro =
            'O valor é maior que o saldo devedor '
            '(${formatarMoeda(widget.saldo)}).',
      );
      return;
    }
    Navigator.of(context).pop(v);
  }

  @override
  Widget build(BuildContext context) {
    final atalhos = <(String, double)>[
      if (widget.saldo > 0) ('Tudo', widget.saldo),
      if (widget.saldo >= 100)
        ('Metade', (widget.saldo / 2 * 100).round() / 100),
      for (final v in const [50.0, 100.0, 200.0])
        if (v < widget.saldo) (formatarMoeda(v).replaceAll(',00', ''), v),
    ];

    return Padding(
      padding: EdgeInsets.fromLTRB(
        20,
        0,
        20,
        20 + MediaQuery.of(context).viewInsets.bottom,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Receber de ${widget.nome}',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 4),
          Text(
            'Deve ${formatarMoeda(widget.saldo)}',
            style: TextStyle(color: VertexColors.textoSecundario),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _controller,
            autofocus: true,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: [
              FilteringTextInputFormatter.allow(RegExp(r'[0-9.,]')),
            ],
            onChanged: (_) => setState(() => _erro = null),
            onSubmitted: (_) => _confirmar(),
            style: const TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.w700,
              fontFeatures: tabular,
            ),
            decoration: InputDecoration(
              labelText: 'Valor recebido',
              prefixText: 'R\$ ',
              errorText: _erro,
            ),
          ),
          if (atalhos.isNotEmpty) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final (rotulo, v) in atalhos)
                  ActionChip(label: Text(rotulo), onPressed: () => _usar(v)),
              ],
            ),
          ],
          const SizedBox(height: 20),
          FilledButton(
            style: FilledButton.styleFrom(minimumSize: const Size(64, 52)),
            onPressed: _confirmar,
            child: const Text('Registrar recebimento'),
          ),
        ],
      ),
    );
  }
}
