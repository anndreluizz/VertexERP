import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/formatadores.dart';
import '../../core/providers.dart';
import '../../models/cliente.dart';
import '../../models/movimento_fiado.dart';
import '../../theme/lista_agrupada.dart';
import '../../theme/skeleton.dart';
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
    final estatisticasAsync = ref.watch(
      estatisticasClienteProvider(cliente.id),
    );

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(saldoFiadoProvider(cliente.id));
        ref.invalidate(historicoFiadoProvider(cliente.id));
        await ref.read(historicoFiadoProvider(cliente.id).future);
      },
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _Cabecalho(cliente: cliente),
          const SizedBox(height: 16),
          saldoAsync.when(
            loading: () => const SkeletonBox(height: 118, borderRadius: 16),
            error: (erro, _) =>
                _PainelSaldo(saldo: null, limite: cliente.limiteCredito),
            data: (saldo) =>
                _PainelSaldo(saldo: saldo, limite: cliente.limiteCredito),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _AcaoRapida(
                  icone: Icons.point_of_sale_outlined,
                  rotulo: 'Vender',
                  aoTocar: () {
                    ref.read(abaSelecionadaProvider.notifier).state = 1;
                    Navigator.of(context).pop();
                  },
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _AcaoRapida(
                  icone: Icons.payments_outlined,
                  rotulo: 'Receber',
                  aoTocar: () => _abrirReceber(context, ref),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(child: _botaoMenuWhatsapp(context, ref)),
            ],
          ),
          estatisticasAsync.when(
            loading: () => const SizedBox.shrink(),
            error: (erro, _) => const SizedBox.shrink(),
            data: (estatisticas) => Padding(
              padding: const EdgeInsets.only(top: 12),
              child: _Estatisticas(
                itens: [
                  (
                    'Última compra',
                    estatisticas.ultimaCompra != null
                        ? formatarData(estatisticas.ultimaCompra!)
                        : '—',
                  ),
                  ('Total', formatarMoeda(estatisticas.totalComprado)),
                  ('Compras', '${estatisticas.qtdCompras}'),
                ],
              ),
            ),
          ),
          const CabecalhoGrupo('Histórico financeiro'),
          historicoAsync.when(
            loading: () => const SkeletonListCard(),
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

              return ListaAgrupada(
                recuo: 48,
                linhas: [
                  for (final movimento in movimentos)
                    _linhaMovimento(context, movimento),
                ],
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
        PopupMenuItem(value: _AcaoWhatsapp.haver, child: Text('Enviar Haver')),
        PopupMenuItem(
          value: _AcaoWhatsapp.cadastro,
          child: Text('Enviar Cadastro do Cliente'),
        ),
      ],
      child: IgnorePointer(
        child: _AcaoRapida(
          icone: Icons.chat_outlined,
          rotulo: 'WhatsApp',
          aoTocar: cliente.telefone == null ? null : () {},
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
      SnackBar(content: Text(erro ?? 'Recebimento registrado com sucesso.')),
    );
  }

  Widget _linhaMovimento(BuildContext context, MovimentoFiado movimento) {
    final compra = movimento.tipo == 'COMPRA';

    final IconData iconeMovimento;
    final Color cor;
    final String descricaoPadrao;

    if (compra) {
      iconeMovimento = Icons.shopping_bag_outlined;
      cor = VertexColors.erro;
      descricaoPadrao = 'Compra a prazo';
    } else if (movimento.tipo == 'HAVER') {
      iconeMovimento = Icons.savings_outlined;
      cor = VertexColors.alerta;
      descricaoPadrao = 'Crédito (Haver)';
    } else {
      iconeMovimento = Icons.payments_outlined;
      cor = VertexColors.secundaria;
      descricaoPadrao = 'Pagamento';
    }

    final tema = Theme.of(context).textTheme;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          Icon(iconeMovimento, size: 18, color: cor),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  movimento.descricao ?? descricaoPadrao,
                  style: tema.titleSmall,
                ),
                const SizedBox(height: 2),
                Text(formatarData(movimento.data), style: tema.bodySmall),
              ],
            ),
          ),
          Text(
            '${compra ? '+' : '-'} ${formatarMoeda(movimento.valor)}',
            style: tema.titleSmall?.copyWith(
              fontWeight: FontWeight.w700,
              color: cor,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
        ],
      ),
    );
  }
}

enum _AcaoWhatsapp { extrato, cobranca, saldo, haver, cadastro }

class _Cabecalho extends StatelessWidget {
  const _Cabecalho({required this.cliente});

  final Cliente cliente;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    final partes = cliente.nome
        .trim()
        .split(RegExp(r'\s+'))
        .where((p) => p.isNotEmpty);
    final iniciais = partes.isEmpty
        ? '?'
        : (partes.first[0] + (partes.length > 1 ? partes.last[0] : ''))
              .toUpperCase();
    final contatos = <(IconData, String)>[
      if (cliente.telefone != null) (Icons.phone_outlined, cliente.telefone!),
      if (cliente.email != null) (Icons.mail_outline, cliente.email!),
      if (cliente.enderecoCompleto.isNotEmpty)
        (Icons.location_on_outlined, cliente.enderecoCompleto),
    ];

    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 4, 4, 0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 56,
            height: 56,
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
                Text(cliente.nome, style: tema.headlineSmall),
                const SizedBox(height: 2),
                Text(
                  'Cliente desde ${formatarData(cliente.criadoEm)}',
                  style: tema.bodySmall,
                ),
                for (final (icone, texto) in contatos) ...[
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      Icon(icone, size: 15, color: VertexColors.textoTerciario),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          texto,
                          style: tema.bodyMedium?.copyWith(
                            color: VertexColors.textoSecundario,
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Saldo devedor + quanto do limite de credito ja foi usado -- a
/// pergunta que o dono faz ao abrir a ficha ("quanto ele me deve, e
/// ainda pode comprar fiado?").
class _PainelSaldo extends StatelessWidget {
  const _PainelSaldo({required this.saldo, required this.limite});

  final double? saldo;
  final double? limite;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    final valor = saldo;
    final devendo = (valor ?? 0) > 0;
    final temLimite = limite != null && limite! > 0;
    final uso = temLimite && valor != null
        ? (valor / limite!).clamp(0.0, 1.0)
        : 0.0;
    final estourou = temLimite && valor != null && valor > limite!;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('SALDO DEVEDOR', style: tema.labelSmall),
            const SizedBox(height: 6),
            Text(
              valor == null ? '—' : formatarMoeda(valor),
              style: tema.headlineMedium?.copyWith(
                color: devendo ? VertexColors.erro : VertexColors.secundaria,
              ),
            ),
            if (temLimite) ...[
              const SizedBox(height: 14),
              ClipRRect(
                borderRadius: BorderRadius.circular(99),
                child: LinearProgressIndicator(
                  value: uso,
                  minHeight: 6,
                  backgroundColor: VertexColors.fundo,
                  color: estourou
                      ? VertexColors.erro
                      : uso > 0.8
                      ? VertexColors.alerta
                      : VertexColors.primaria,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                estourou
                    ? 'Acima do limite de ${formatarMoeda(limite!)}'
                    : 'Limite ${formatarMoeda(limite!)} · disponível '
                          '${formatarMoeda(limite! - (valor ?? 0))}',
                style: tema.bodySmall?.copyWith(
                  color: estourou ? VertexColors.erro : null,
                  fontWeight: estourou ? FontWeight.w600 : null,
                ),
              ),
            ] else ...[
              const SizedBox(height: 4),
              Text('Sem limite de crédito definido', style: tema.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}

class _AcaoRapida extends StatelessWidget {
  const _AcaoRapida({
    required this.icone,
    required this.rotulo,
    required this.aoTocar,
  });

  final IconData icone;
  final String rotulo;
  final VoidCallback? aoTocar;

  @override
  Widget build(BuildContext context) {
    final ativo = aoTocar != null;
    final cor = ativo ? VertexColors.primaria : VertexColors.textoTerciario;

    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: aoTocar,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 14),
          child: Column(
            children: [
              Icon(icone, size: 22, color: cor),
              const SizedBox(height: 6),
              Text(
                rotulo,
                maxLines: 1,
                style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: ativo
                      ? VertexColors.texto
                      : VertexColors.textoTerciario,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Estatisticas extends StatelessWidget {
  const _Estatisticas({required this.itens});

  final List<(String, String)> itens;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;

    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 14),
        child: IntrinsicHeight(
          child: Row(
            children: [
              for (var i = 0; i < itens.length; i++) ...[
                if (i > 0) const VerticalDivider(width: 1),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(itens[i].$1, style: tema.labelMedium, maxLines: 1),
                        const SizedBox(height: 4),
                        FittedBox(
                          fit: BoxFit.scaleDown,
                          alignment: Alignment.centerLeft,
                          child: Text(
                            itens[i].$2,
                            style: tema.titleSmall?.copyWith(
                              fontWeight: FontWeight.w700,
                              fontFeatures: const [
                                FontFeature.tabularFigures(),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
