import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../core/api_client.dart';
import '../../core/providers.dart';
import '../../theme/vertex_colors.dart';
import '../financeiro/escolher_anexo.dart';
import '../financeiro/financeiro_provider.dart' show AnexoEscolhido;
import 'estoque_provider.dart';

/// Novo produto pelo celular: o essencial do cartao "Principal" do
/// Desktop (codigo, nome, categoria, precos, estoque) + foto. Codigo
/// lido pela camera; codigo que ja existe vira entrada de estoque,
/// mesma regra do Desktop.
class CadastroProdutoScreen extends ConsumerStatefulWidget {
  const CadastroProdutoScreen({super.key});

  @override
  ConsumerState<CadastroProdutoScreen> createState() =>
      _CadastroProdutoScreenState();
}

class _CadastroProdutoScreenState extends ConsumerState<CadastroProdutoScreen> {
  final _codigo = TextEditingController();
  final _nome = TextEditingController();
  final _categoria = TextEditingController();
  final _precoVenda = TextEditingController();
  final _precoCusto = TextEditingController();
  final _estoque = TextEditingController();
  List<String> _categorias = const [];
  AnexoEscolhido? _foto;
  bool _enviando = false;

  Map<String, dynamic>? get _comLoja {
    final lojaId = ref.read(lojaFiltroProvider);
    return lojaId != null ? {'loja_id': lojaId} : null;
  }

  @override
  void initState() {
    super.initState();
    _carregarCategorias();
  }

  @override
  void dispose() {
    for (final c in [
      _codigo,
      _nome,
      _categoria,
      _precoVenda,
      _precoCusto,
      _estoque,
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _carregarCategorias() async {
    try {
      final resposta = await ref
          .read(apiClientProvider)
          .dio
          .get('/categorias/');
      final nomes = [
        for (final c in resposta.data as List<dynamic>)
          if (c['ativo'] == true) c['nome'] as String,
      ]..sort();
      if (mounted) setState(() => _categorias = nomes);
    } catch (_) {
      // sem a lista ainda da' pra digitar a categoria
    }
  }

  void _avisar(String texto) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(texto)));
  }

  Future<void> _lerCodigo() async {
    final codigo = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (_) => const _LeitorCodigoScreen()),
    );
    if (codigo == null || !mounted) return;
    _codigo.text = codigo;
    await _conferirCodigo();
  }

  /// Codigo ja cadastrado? Oferece somar ao estoque em vez de
  /// cadastrar de novo (GET /pdv/produto acha por codigo interno ou
  /// de barras -- a mesma busca do Desktop).
  Future<void> _conferirCodigo() async {
    final codigo = _codigo.text.trim();
    if (codigo.isEmpty) return;

    final Map<String, dynamic> produto;
    try {
      final resposta = await ref
          .read(apiClientProvider)
          .dio
          .get(
            '/pdv/produto/${Uri.encodeComponent(codigo)}',
            queryParameters: _comLoja,
          );
      produto = resposta.data as Map<String, dynamic>;
    } on DioException catch (e) {
      // servidor respondeu "nao achei" = produto novo, segue o cadastro
      if (e.response == null && mounted) {
        _avisar('Sem conexão com o servidor para conferir o código.');
      }
      return;
    }
    if (!mounted) return;

    final quantidade = await showDialog<int>(
      context: context,
      builder: (_) => _SomarEstoqueDialog(produto: produto),
    );
    if (!mounted) return;

    if (quantidade != null) {
      try {
        await ref
            .read(apiClientProvider)
            .dio
            .post(
              '/estoque/movimentos',
              queryParameters: _comLoja,
              data: {
                'produto_id': produto['id'],
                'tipo': 'ENTRADA',
                'quantidade': quantidade,
                'motivo': 'Entrada pelo cadastro de produto (app)',
              },
            );
        ref.invalidate(produtosProvider);
        if (mounted) {
          _avisar(
            '+$quantidade em ${produto['nome']} '
            '(agora ${(produto['estoque'] as int) + quantidade}).',
          );
        }
      } catch (e) {
        if (mounted) {
          _avisar(
            mensagemDeErro(
              e,
              fallback: 'Não foi possível adicionar ao estoque.',
            ),
          );
        }
      }
    }
    _codigo.clear();
  }

  /// "12,50" e "1.234,50" (teclado BR) e "12.50" (teclado US).
  double? _valor(TextEditingController c) {
    final t = c.text.trim();
    return double.tryParse(
      t.contains(',') ? t.replaceAll('.', '').replaceAll(',', '.') : t,
    );
  }

  Future<void> _salvar() async {
    final nome = _nome.text.trim().toUpperCase();
    final precoVenda = _valor(_precoVenda);
    if (nome.isEmpty) return _avisar('Informe o nome do produto.');
    if (precoVenda == null || precoVenda <= 0) {
      return _avisar('Informe o preço de venda.');
    }

    final codigoBarras = _codigo.text.trim();
    setState(() => _enviando = true);
    try {
      await ref
          .read(apiClientProvider)
          .dio
          .post(
            '/produtos/',
            queryParameters: _comLoja,
            data: {
              // vazio = backend gera o proximo codigo interno (0001...)
              'codigo': codigoBarras,
              'codigo_barras': codigoBarras.isEmpty ? null : codigoBarras,
              'nome': nome,
              'categoria': _categoria.text.trim().isEmpty
                  ? null
                  : _categoria.text.trim().toUpperCase(),
              'preco_venda': precoVenda,
              'preco_custo': _valor(_precoCusto) ?? 0,
              'estoque': int.tryParse(_estoque.text.trim()) ?? 0,
              'foto_base64': _foto == null ? null : base64Encode(_foto!.bytes),
            },
          );
      ref.invalidate(produtosProvider);
      if (!mounted) return;
      _avisar('$nome cadastrado.');
      // pronto pro proximo produto
      for (final c in [_codigo, _nome, _precoVenda, _precoCusto, _estoque]) {
        c.clear();
      }
      setState(() => _foto = null);
    } catch (e) {
      if (mounted) {
        _avisar(
          mensagemDeErro(e, fallback: 'Não foi possível cadastrar o produto.'),
        );
      }
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  InputDecoration _campo(String rotulo, {String? prefixo}) => InputDecoration(
    labelText: rotulo,
    prefixText: prefixo,
    border: const OutlineInputBorder(),
  );

  @override
  Widget build(BuildContext context) {
    const numero = TextInputType.numberWithOptions(decimal: true);

    return Scaffold(
      appBar: AppBar(title: const Text('Novo produto')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            TextField(
              controller: _codigo,
              textInputAction: TextInputAction.next,
              onSubmitted: (_) => _conferirCodigo(),
              decoration: _campo('Código de barras').copyWith(
                helperText: 'Vazio = o sistema gera um código interno',
                suffixIcon: IconButton(
                  tooltip: 'Ler com a câmera',
                  icon: const Icon(Icons.qr_code_scanner),
                  onPressed: _lerCodigo,
                ),
              ),
            ),
            const SizedBox(height: 14),
            TextField(
              controller: _nome,
              textCapitalization: TextCapitalization.characters,
              textInputAction: TextInputAction.next,
              decoration: _campo('Nome'),
            ),
            const SizedBox(height: 14),
            DropdownMenu<String>(
              controller: _categoria,
              expandedInsets: EdgeInsets.zero,
              enableFilter: true,
              requestFocusOnTap: true,
              label: const Text('Categoria'),
              dropdownMenuEntries: [
                for (final c in _categorias)
                  DropdownMenuEntry(value: c, label: c),
              ],
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _precoVenda,
                    keyboardType: numero,
                    decoration: _campo('Preço de venda', prefixo: 'R\$ '),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    controller: _precoCusto,
                    keyboardType: numero,
                    decoration: _campo('Custo', prefixo: 'R\$ '),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            TextField(
              controller: _estoque,
              keyboardType: TextInputType.number,
              decoration: _campo('Estoque inicial'),
            ),
            const SizedBox(height: 14),
            OutlinedButton.icon(
              onPressed: () async {
                final foto = await escolherAnexoComprovante(context);
                if (foto != null && mounted) setState(() => _foto = foto);
              },
              icon: Icon(
                _foto == null
                    ? Icons.photo_camera_outlined
                    : Icons.check_circle_outline,
              ),
              label: Text(_foto == null ? 'Foto (opcional)' : 'Foto escolhida'),
            ),
            const SizedBox(height: 28),
            FilledButton(
              onPressed: _enviando ? null : _salvar,
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
                  : const Text('Cadastrar'),
            ),
          ],
        ),
      ),
    );
  }
}

class _SomarEstoqueDialog extends StatefulWidget {
  const _SomarEstoqueDialog({required this.produto});

  final Map<String, dynamic> produto;

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
    final p = widget.produto;
    return AlertDialog(
      title: const Text('Produto já cadastrado'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${p['nome']} (código ${p['codigo']}, '
            'estoque atual ${p['estoque']}).\n\n'
            'Quantas unidades adicionar ao estoque?',
          ),
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

class _LeitorCodigoScreen extends StatefulWidget {
  const _LeitorCodigoScreen();

  @override
  State<_LeitorCodigoScreen> createState() => _LeitorCodigoScreenState();
}

class _LeitorCodigoScreenState extends State<_LeitorCodigoScreen> {
  bool _lido = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Aponte para o código')),
      body: MobileScanner(
        onDetect: (captura) {
          final valor = captura.barcodes.firstOrNull?.rawValue;
          // a camera detecta varias vezes por segundo -- sai so' uma
          if (_lido || valor == null || valor.isEmpty) return;
          _lido = true;
          Navigator.of(context).pop(valor);
        },
      ),
    );
  }
}
