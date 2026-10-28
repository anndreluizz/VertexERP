import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/api_client.dart';
import '../../core/formatadores.dart';
import '../../core/providers.dart';
import '../../models/produto.dart';
import '../../theme/lista_agrupada.dart';
import '../../theme/skeleton.dart';
import '../../theme/vertex_colors.dart';
import 'estoque_provider.dart';

/// Vitrine (site da loja): por/tirar produto do site, destaque e foto
/// tirada na hora. Mesmo PUT parcial da aba Vitrine do Desktop; o site
/// pega a mudanca na proxima publicacao automatica (ate' 5 minutos).

enum FiltroVitrine { noSite, pendencias, todos }

final filtroVitrineProvider = StateProvider.autoDispose<FiltroVitrine>(
  (ref) => FiltroVitrine.noSite,
);

final buscaVitrineProvider = StateProvider.autoDispose<String>((ref) => '');

/// O que deixa o produto feio ou escondido no site.
List<String> pendenciasVitrine(Produto p) => [
  if (!p.temFoto) 'sem foto',
  if ((p.categoria ?? '').isEmpty) 'sem categoria',
  if (p.semEstoque) 'sem estoque',
];

bool passaFiltroVitrine(Produto p, FiltroVitrine filtro, String busca) {
  if (busca.isNotEmpty) {
    return p.nome.toLowerCase().contains(busca) ||
        p.codigo.toLowerCase().contains(busca);
  }
  return switch (filtro) {
    FiltroVitrine.noSite => p.vitrinePublicar,
    FiltroVitrine.pendencias =>
      p.vitrinePublicar && pendenciasVitrine(p).isNotEmpty,
    FiltroVitrine.todos => true,
  };
}

class VitrineScreen extends ConsumerWidget {
  const VitrineScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final filtro = ref.watch(filtroVitrineProvider);
    final busca = ref.watch(buscaVitrineProvider).trim().toLowerCase();
    final produtosAsync = ref.watch(produtosProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Vitrine')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: TextField(
              onChanged: (texto) =>
                  ref.read(buscaVitrineProvider.notifier).state = texto,
              decoration: const InputDecoration(
                hintText: 'Buscar por nome ou código',
                prefixIcon: Icon(Icons.search),
                border: OutlineInputBorder(),
                isDense: true,
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
            child: Wrap(
              spacing: 8,
              children: [
                for (final (valor, rotulo) in const [
                  (FiltroVitrine.noSite, 'No site'),
                  (FiltroVitrine.pendencias, 'Com pendência'),
                  (FiltroVitrine.todos, 'Todos'),
                ])
                  ChoiceChip(
                    label: Text(rotulo),
                    selected: filtro == valor,
                    onSelected: (_) =>
                        ref.read(filtroVitrineProvider.notifier).state = valor,
                  ),
              ],
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => ref.refresh(produtosProvider.future),
              child: produtosAsync.when(
                loading: () => const SkeletonList(),
                error: (erro, _) => ListView(
                  children: const [
                    SizedBox(height: 80),
                    Center(
                      child: Text('Não foi possível carregar os produtos.'),
                    ),
                  ],
                ),
                data: (produtos) {
                  final filtrados =
                      produtos
                          .where((p) => passaFiltroVitrine(p, filtro, busca))
                          .toList()
                        ..sort((a, b) => a.nome.compareTo(b.nome));
                  final noSite = produtos
                      .where((p) => p.vitrinePublicar)
                      .length;

                  if (filtrados.isEmpty) {
                    return ListView(
                      padding: const EdgeInsets.all(32),
                      children: [
                        const SizedBox(height: 48),
                        Text(
                          filtro == FiltroVitrine.noSite && busca.isEmpty
                              ? 'Nenhum produto no site ainda.\n'
                                    'Toque em "Todos" e ligue "No site" nos que quiser mostrar.'
                              : 'Nenhum produto encontrado.',
                          textAlign: TextAlign.center,
                        ),
                      ],
                    );
                  }

                  return ListView(
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                    children: [
                      CabecalhoGrupo(
                        '$noSite no site · o site atualiza em até 5 min',
                      ),
                      ListaAgrupada(
                        linhas: [
                          for (final produto in filtrados)
                            _LinhaVitrine(produto: produto),
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
    );
  }
}

class _LinhaVitrine extends ConsumerStatefulWidget {
  const _LinhaVitrine({required this.produto});

  final Produto produto;

  @override
  ConsumerState<_LinhaVitrine> createState() => _LinhaVitrineState();
}

class _LinhaVitrineState extends ConsumerState<_LinhaVitrine> {
  bool _salvando = false;

  Future<void> _alterar({
    required bool publicar,
    required bool destaque,
  }) async {
    final p = widget.produto;
    setState(() => _salvando = true);
    try {
      // parcial: codigo/nome exigidos pelo schema, o resto fica como esta'
      await ref
          .read(apiClientProvider)
          .dio
          .put(
            '/produtos/${p.id}',
            data: {
              'codigo': p.codigo,
              'nome': p.nome,
              'vitrine_publicar': publicar,
              'vitrine_destaque': destaque && publicar,
            },
          );
      ref.invalidate(produtosProvider);
    } catch (e) {
      _avisar(
        mensagemDeErro(e, fallback: 'Não foi possível alterar a vitrine.'),
      );
    } finally {
      if (mounted) setState(() => _salvando = false);
    }
  }

  Future<void> _tirarFoto() async {
    final origem = await showModalBottomSheet<ImageSource>(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.photo_camera_outlined),
              title: const Text('Tirar foto'),
              onTap: () => Navigator.of(context).pop(ImageSource.camera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('Escolher da galeria'),
              onTap: () => Navigator.of(context).pop(ImageSource.gallery),
            ),
          ],
        ),
      ),
    );
    if (origem == null) return;

    // 1200px e' o bastante pro site e nao pesa no 4G
    final arquivo = await ImagePicker().pickImage(
      source: origem,
      maxWidth: 1200,
      maxHeight: 1200,
      imageQuality: 80,
    );
    if (arquivo == null) return;

    setState(() => _salvando = true);
    try {
      final bytes = await arquivo.readAsBytes();
      await ref
          .read(apiClientProvider)
          .dio
          .post(
            '/produtos/${widget.produto.id}/fotos',
            data: {'imagem_base64': base64Encode(bytes), 'principal': true},
          );
      ref.invalidate(produtosProvider);
      _avisar('Foto salva. Ela aparece no site em até 5 minutos.');
    } catch (e) {
      _avisar(mensagemDeErro(e, fallback: 'Não foi possível salvar a foto.'));
    } finally {
      if (mounted) setState(() => _salvando = false);
    }
  }

  void _avisar(String texto) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(texto)));
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.produto;
    final tema = Theme.of(context).textTheme;
    final pendencias = p.vitrinePublicar
        ? pendenciasVitrine(p)
        : const <String>[];

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 8, 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      p.nome,
                      style: tema.titleSmall,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${p.codigo} · ${formatarMoeda(p.precoVenda)} · ${p.estoque} un.',
                      style: tema.bodySmall,
                    ),
                  ],
                ),
              ),
              IconButton(
                tooltip: p.temFoto ? 'Trocar foto' : 'Tirar foto',
                onPressed: _salvando ? null : _tirarFoto,
                icon: Icon(
                  p.temFoto
                      ? Icons.photo_camera_outlined
                      : Icons.add_a_photo_outlined,
                  color: p.temFoto ? null : VertexColors.alerta,
                ),
              ),
            ],
          ),
          Row(
            children: [
              _Interruptor(
                rotulo: 'No site',
                valor: p.vitrinePublicar,
                aoMudar: _salvando
                    ? null
                    : (v) => _alterar(publicar: v, destaque: p.vitrineDestaque),
              ),
              const SizedBox(width: 16),
              _Interruptor(
                rotulo: 'Destaque',
                valor: p.vitrineDestaque,
                // destaque so' vale pra quem esta' no site (igual ao Desktop)
                aoMudar: _salvando || !p.vitrinePublicar
                    ? null
                    : (v) => _alterar(publicar: true, destaque: v),
              ),
              if (_salvando) ...[
                const SizedBox(width: 12),
                const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              ],
            ],
          ),
          if (pendencias.isNotEmpty)
            Text(
              '${pendencias.join(', ')[0].toUpperCase()}${pendencias.join(', ').substring(1)}',
              style: tema.labelSmall?.copyWith(
                color: VertexColors.alerta,
                letterSpacing: 0,
              ),
            ),
        ],
      ),
    );
  }
}

class _Interruptor extends StatelessWidget {
  const _Interruptor({
    required this.rotulo,
    required this.valor,
    required this.aoMudar,
  });

  final String rotulo;
  final bool valor;
  final ValueChanged<bool>? aoMudar;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Switch(value: valor, onChanged: aoMudar),
        Text(rotulo, style: Theme.of(context).textTheme.bodyMedium),
      ],
    );
  }
}
