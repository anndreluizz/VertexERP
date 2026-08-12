import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/cliente.dart';
import '../models/produto.dart';
import '../models/venda.dart';
import '../services/api_client.dart';
import '../services/cliente_service.dart';
import '../services/produto_service.dart';
import '../services/sessao_provider.dart';
import '../services/venda_service.dart';

class _ItemCarrinho {
  final Produto produto;
  int quantidade;

  _ItemCarrinho(this.produto, this.quantidade);

  double get subtotal => produto.precoVenda * quantidade;
}

class PedidoScreen extends StatefulWidget {
  const PedidoScreen({super.key});

  @override
  State<PedidoScreen> createState() => _PedidoScreenState();
}

class _PedidoScreenState extends State<PedidoScreen> {
  static final _moeda = NumberFormat.currency(locale: 'pt_BR', symbol: 'R\$');

  List<Produto> _produtos = [];
  List<Cliente> _clientes = [];
  final Map<int, _ItemCarrinho> _carrinho = {};

  Cliente? _clienteSelecionado;
  FormaPagamento _formaPagamento = FormaPagamento.dinheiro;
  final _descontoController = TextEditingController(text: '0');

  bool _carregando = true;
  bool _enviando = false;
  String? _erro;

  @override
  void initState() {
    super.initState();
    _carregarDados();
  }

  @override
  void dispose() {
    _descontoController.dispose();
    super.dispose();
  }

  Future<void> _carregarDados() async {
    setState(() {
      _carregando = true;
      _erro = null;
    });
    final sessao = context.read<SessaoProvider>();
    try {
      final produtoService = ProdutoService(sessao.client);
      final clienteService = ClienteService(sessao.client);
      final resultados = await Future.wait([
        produtoService.listar(),
        clienteService.listar(),
      ]);
      setState(() {
        _produtos = resultados[0] as List<Produto>;
        _clientes = resultados[1] as List<Cliente>;
      });
    } on UnauthorizedException {
      if (mounted) await context.read<SessaoProvider>().logout();
    } on ApiException catch (e) {
      setState(() => _erro = e.message);
    } catch (e) {
      setState(() => _erro = 'Não foi possível carregar os dados.');
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  void _adicionar(Produto produto) {
    setState(() {
      final item = _carrinho[produto.id];
      if (item != null) {
        item.quantidade++;
      } else {
        _carrinho[produto.id] = _ItemCarrinho(produto, 1);
      }
    });
  }

  void _remover(Produto produto) {
    setState(() {
      final item = _carrinho[produto.id];
      if (item == null) return;
      if (item.quantidade <= 1) {
        _carrinho.remove(produto.id);
      } else {
        item.quantidade--;
      }
    });
  }

  double get _subtotal =>
      _carrinho.values.fold(0.0, (soma, item) => soma + item.subtotal);

  double get _desconto => double.tryParse(
        _descontoController.text.replaceAll(',', '.'),
      ) ??
      0.0;

  double get _total => (_subtotal - _desconto).clamp(0, double.infinity);

  Future<void> _finalizar() async {
    if (_carrinho.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Adicione ao menos um item ao pedido.')),
      );
      return;
    }

    setState(() => _enviando = true);
    final sessao = context.read<SessaoProvider>();
    try {
      final venda = VendaCreate(
        clienteId: _clienteSelecionado?.id,
        desconto: _desconto,
        formaPagamento: _formaPagamento,
        itens: _carrinho.values
            .map((item) => ItemVendaCreate(
                  produtoId: item.produto.id,
                  quantidade: item.quantidade,
                  valorUnitario: item.produto.precoVenda,
                ))
            .toList(),
      );
      final resposta = await VendaService(sessao.client).criar(venda);

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Pedido #${resposta.id} registrado — ${_moeda.format(resposta.valorTotal)}',
          ),
        ),
      );
      setState(() {
        _carrinho.clear();
        _clienteSelecionado = null;
        _formaPagamento = FormaPagamento.dinheiro;
        _descontoController.text = '0';
      });
    } on UnauthorizedException {
      if (mounted) await context.read<SessaoProvider>().logout();
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.message)),
        );
      }
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Anotar Pedido'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Sair',
            onPressed: () => context.read<SessaoProvider>().logout(),
          ),
        ],
      ),
      body: _buildCorpo(),
    );
  }

  Widget _buildCorpo() {
    if (_carregando) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_erro != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(_erro!),
            const SizedBox(height: 12),
            FilledButton(onPressed: _carregarDados, child: const Text('Tentar novamente')),
          ],
        ),
      );
    }

    return Column(
      children: [
        Expanded(
          child: RefreshIndicator(
            onRefresh: _carregarDados,
            child: ListView.builder(
              itemCount: _produtos.length,
              itemBuilder: (context, index) {
                final produto = _produtos[index];
                final item = _carrinho[produto.id];
                return ListTile(
                  title: Text(produto.nome),
                  subtitle: Text(_moeda.format(produto.precoVenda)),
                  trailing: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      IconButton(
                        icon: const Icon(Icons.remove_circle_outline),
                        onPressed: item == null ? null : () => _remover(produto),
                      ),
                      Text('${item?.quantidade ?? 0}'),
                      IconButton(
                        icon: const Icon(Icons.add_circle_outline),
                        onPressed: () => _adicionar(produto),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        ),
        _buildResumoPedido(),
      ],
    );
  }

  Widget _buildResumoPedido() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        boxShadow: const [BoxShadow(blurRadius: 4, color: Colors.black12)],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          DropdownButtonFormField<Cliente?>(
            initialValue: _clienteSelecionado,
            decoration: const InputDecoration(labelText: 'Cliente (opcional)'),
            items: [
              const DropdownMenuItem<Cliente?>(value: null, child: Text('Sem cliente')),
              ..._clientes.map(
                (c) => DropdownMenuItem<Cliente?>(value: c, child: Text(c.nome)),
              ),
            ],
            onChanged: (valor) => setState(() => _clienteSelecionado = valor),
          ),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _descontoController,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: 'Desconto (R\$)'),
                  onChanged: (_) => setState(() {}),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: DropdownButtonFormField<FormaPagamento>(
                  initialValue: _formaPagamento,
                  decoration: const InputDecoration(labelText: 'Pagamento'),
                  items: FormaPagamento.values
                      .map((f) => DropdownMenuItem(value: f, child: Text(f.rotulo)))
                      .toList(),
                  onChanged: (valor) {
                    if (valor != null) setState(() => _formaPagamento = valor);
                  },
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Total: ${_moeda.format(_total)}',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              FilledButton(
                onPressed: _enviando ? null : _finalizar,
                child: _enviando
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Finalizar pedido'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
