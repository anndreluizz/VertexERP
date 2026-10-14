import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/privacidade.dart';
import '../../theme/componentes.dart';
import '../../theme/lista_agrupada.dart';
import '../../theme/skeleton.dart';
import '../../theme/vertex_colors.dart';
import 'cliente_detalhe_screen.dart';
import 'clientes_provider.dart';

enum _Ordem { maiorSaldo, maisAtrasado, nome }

extension on _Ordem {
  String get rotulo => switch (this) {
    _Ordem.maiorSaldo => 'Maior saldo devedor',
    _Ordem.maisAtrasado => 'Mais tempo sem pagar',
    _Ordem.nome => 'Nome (A-Z)',
  };
}

class ClientesScreen extends ConsumerStatefulWidget {
  const ClientesScreen({super.key});

  @override
  ConsumerState<ClientesScreen> createState() => _ClientesScreenState();
}

class _ClientesScreenState extends ConsumerState<ClientesScreen> {
  _Ordem _ordem = _Ordem.maiorSaldo;

  Future<void> _escolherOrdem() async {
    final escolhida = await showModalBottomSheet<_Ordem>(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final ordem in _Ordem.values)
              ListTile(
                title: Text(ordem.rotulo),
                trailing: ordem == _ordem
                    ? Icon(Icons.check_rounded, color: VertexColors.primaria)
                    : null,
                onTap: () => Navigator.of(context).pop(ordem),
              ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    if (escolhida != null) setState(() => _ordem = escolhida);
  }

  Future<void> _atualizar() async {
    ref.invalidate(clientesProvider);
    ref.invalidate(movimentosFiadoProvider);
    await ref.read(clientesComAnaliseProvider.future);
  }

  @override
  Widget build(BuildContext context) {
    final busca = ref.watch(buscaClientesProvider);
    final filtro = ref.watch(filtroClientesProvider);
    final dadosAsync = ref.watch(clientesComAnaliseProvider);
    final todos = dadosAsync.valueOrNull ?? const [];

    final totalFiado = todos.fold<double>(
      0,
      (s, c) => s + (c.analise.devendo ? c.analise.saldoDevedor : 0),
    );

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            CabecalhoTela(
              titulo: 'Clientes',
              subtitulo: dadosAsync.hasValue
                  ? '${todos.length} cadastrados · '
                        '${moedaTela(totalFiado)} no fiado'
                  : null,
              acao: BotaoIcone(
                icone: Icons.sort_rounded,
                dica: 'Ordenar: ${_ordem.rotulo}',
                aoTocar: _escolherOrdem,
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
              child: TextField(
                onChanged: (valor) =>
                    ref.read(buscaClientesProvider.notifier).state = valor,
                textInputAction: TextInputAction.search,
                decoration: const InputDecoration(
                  prefixIcon: Icon(Icons.search_rounded, size: 20),
                  hintText: 'Buscar por nome, apelido ou telefone',
                ),
              ),
            ),
            SizedBox(
              height: 36,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: FiltroClientes.values.length,
                separatorBuilder: (_, _) => const SizedBox(width: 8),
                itemBuilder: (context, i) {
                  final opcao = FiltroClientes.values[i];
                  final qtd = dadosAsync.hasValue
                      ? todos.where(opcao.aplica).length
                      : null;
                  return ChipFiltro(
                    rotulo: qtd == null
                        ? opcao.rotulo
                        : '${opcao.rotulo} · $qtd',
                    ligado: opcao == filtro,
                    aoTocar: () =>
                        ref.read(filtroClientesProvider.notifier).state = opcao,
                  );
                },
              ),
            ),
            const SizedBox(height: 10),
            Expanded(
              child: RefreshIndicator(
                onRefresh: _atualizar,
                child: dadosAsync.when(
                  loading: () => const SkeletonList(),
                  error: (erro, _) => ListView(
                    children: [
                      const SizedBox(height: 80),
                      const Center(
                        child: Text('Não foi possível carregar os clientes.'),
                      ),
                      const SizedBox(height: 12),
                      Center(
                        child: OutlinedButton(
                          onPressed: _atualizar,
                          child: const Text('Tentar de novo'),
                        ),
                      ),
                    ],
                  ),
                  data: (lista) {
                    final termo = _normalizar(busca.trim());
                    final filtrados = lista
                        .where(filtro.aplica)
                        .where(
                          (c) =>
                              termo.isEmpty ||
                              _normalizar(c.cliente.nome).contains(termo) ||
                              (c.cliente.telefone ?? '').contains(termo),
                        )
                        .toList();
                    _ordenar(filtrados);

                    if (filtrados.isEmpty) {
                      return ListView(
                        children: [
                          const SizedBox(height: 60),
                          Center(
                            child: Padding(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 32,
                              ),
                              child: Text(
                                lista.isEmpty
                                    ? 'Nenhum cliente cadastrado ainda.'
                                    : 'Nenhum cliente encontrado. Tente outro '
                                          'nome ou toque em “Todos”.',
                                textAlign: TextAlign.center,
                                style: TextStyle(
                                  color: VertexColors.textoSecundario,
                                ),
                              ),
                            ),
                          ),
                        ],
                      );
                    }

                    return ListView(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                      children: [
                        ListaAgrupada(
                          recuo: 68,
                          linhas: [
                            for (final item in filtrados)
                              _LinhaCliente(item: item),
                          ],
                        ),
                      ],
                    );
                  },
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _ordenar(List<ClienteComAnalise> lista) {
    switch (_ordem) {
      case _Ordem.maiorSaldo:
        lista.sort(
          (a, b) => b.analise.saldoDevedor.compareTo(a.analise.saldoDevedor),
        );
      case _Ordem.maisAtrasado:
        lista.sort(
          (a, b) => (b.analise.diasEmAtraso ?? -1).compareTo(
            a.analise.diasEmAtraso ?? -1,
          ),
        );
      case _Ordem.nome:
        lista.sort(
          (a, b) => _normalizar(
            a.cliente.nome,
          ).compareTo(_normalizar(b.cliente.nome)),
        );
    }
  }
}

/// busca sem acento e sem diferenciar maiuscula ("joao" acha "JOÃO")
String _normalizar(String texto) {
  const de = 'áàâãäéèêëíìîïóòôõöúùûüç';
  const para = 'aaaaaeeeeiiiiooooouuuuc';
  final minusculo = texto.toLowerCase();
  final saida = StringBuffer();
  for (final r in minusculo.runes) {
    final ch = String.fromCharCode(r);
    final i = de.indexOf(ch);
    saida.write(i >= 0 ? para[i] : ch);
  }
  return saida.toString();
}

String _tempo(int? dias) {
  if (dias == null) return '';
  if (dias == 0) return 'hoje';
  if (dias == 1) return 'ontem';
  return 'há $dias dias';
}

class _LinhaCliente extends StatelessWidget {
  const _LinhaCliente({required this.item});

  final ClienteComAnalise item;

  @override
  Widget build(BuildContext context) {
    final analise = item.analise;
    final (fundo, cor, corBarra) = coresStatusCliente(analise.status);
    final uso = item.usoLimite;

    final ultimaMov = analise.ultimaMovimentacao;
    final diasSemMov = ultimaMov == null
        ? null
        : DateTime.now().difference(ultimaMov).inDays.clamp(0, 99999);
    final detalhe = [
      if (uso != null) '${(uso * 100).round()}% do limite',
      if (diasSemMov != null) _tempo(diasSemMov),
    ].join(' · ');

    return InkWell(
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute(
          builder: (context) =>
              ClienteDetalheScreen(clienteId: item.cliente.id),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          children: [
            AvatarIniciais(nome: item.cliente.nome, fundo: fundo, cor: cor),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.cliente.nome,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      if (uso != null) ...[
                        Expanded(
                          child: BarraProgresso(fracao: uso, cor: corBarra),
                        ),
                        const SizedBox(width: 8),
                      ],
                      Flexible(
                        flex: uso != null ? 0 : 1,
                        child: Text(
                          detalhe,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: 12,
                            color: VertexColors.textoSecundario,
                            fontFeatures: tabular,
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  moedaTela(analise.devendo ? analise.saldoDevedor : 0),
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    fontFeatures: tabular,
                  ),
                ),
                const SizedBox(height: 4),
                SeloStatusCliente(analise.status),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
