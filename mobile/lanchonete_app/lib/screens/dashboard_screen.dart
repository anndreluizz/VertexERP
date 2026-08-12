import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/dashboard_resumo.dart';
import '../services/api_client.dart';
import '../services/dashboard_service.dart';
import '../services/sessao_provider.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  static final _moeda = NumberFormat.currency(locale: 'pt_BR', symbol: 'R\$');

  DashboardResumo? _resumo;
  bool _carregando = true;
  String? _erro;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    setState(() {
      _carregando = true;
      _erro = null;
    });
    final sessao = context.read<SessaoProvider>();
    try {
      final resumo = await DashboardService(sessao.client).resumo();
      setState(() => _resumo = resumo);
    } on UnauthorizedException {
      if (mounted) await context.read<SessaoProvider>().logout();
    } on ApiException catch (e) {
      setState(() => _erro = e.message);
    } catch (e) {
      setState(() => _erro = 'Não foi possível carregar o resumo.');
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Gerenciamento'),
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
            FilledButton(onPressed: _carregar, child: const Text('Tentar novamente')),
          ],
        ),
      );
    }

    final resumo = _resumo!;
    final cartoes = [
      _Cartao('Vendas hoje', _moeda.format(resumo.vendasHoje), Icons.point_of_sale),
      _Cartao('Compras hoje', _moeda.format(resumo.comprasHoje), Icons.shopping_cart),
      _Cartao('Saldo em caixa', _moeda.format(resumo.saldoCaixa), Icons.account_balance_wallet),
      _Cartao('Contas a receber', _moeda.format(resumo.contasReceber), Icons.arrow_downward),
      _Cartao('Contas a pagar', _moeda.format(resumo.contasPagar), Icons.arrow_upward),
      _Cartao('Estoque baixo', '${resumo.estoqueBaixo} produto(s)', Icons.warning_amber),
      _Cartao('Produtos cadastrados', '${resumo.produtos}', Icons.fastfood),
      _Cartao('Clientes ativos', '${resumo.clientes}', Icons.people),
      _Cartao('Fornecedores', '${resumo.fornecedores}', Icons.local_shipping),
    ];

    return RefreshIndicator(
      onRefresh: _carregar,
      child: GridView.builder(
        padding: const EdgeInsets.all(16),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          mainAxisSpacing: 12,
          crossAxisSpacing: 12,
          childAspectRatio: 1.3,
        ),
        itemCount: cartoes.length,
        itemBuilder: (context, index) => cartoes[index],
      ),
    );
  }
}

class _Cartao extends StatelessWidget {
  final String titulo;
  final String valor;
  final IconData icone;

  const _Cartao(this.titulo, this.valor, this.icone);

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Icon(icone, color: Theme.of(context).colorScheme.primary),
            Text(titulo, style: Theme.of(context).textTheme.bodySmall),
            Text(
              valor,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
            ),
          ],
        ),
      ),
    );
  }
}
