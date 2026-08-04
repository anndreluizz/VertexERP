import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../models/cliente.dart';
import '../../theme/vertex_colors.dart';
import 'cliente_detalhe_screen.dart';
import 'clientes_provider.dart';

class ClientesScreen extends ConsumerWidget {
  const ClientesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final busca = ref.watch(buscaClientesProvider);
    final clientesAsync = ref.watch(clientesProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Clientes')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: TextField(
              decoration: const InputDecoration(
                prefixIcon: Icon(Icons.search, size: 20),
                hintText: 'Buscar por nome ou telefone...',
              ),
              onChanged: (valor) =>
                  ref.read(buscaClientesProvider.notifier).state = valor,
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => ref.refresh(clientesProvider.future),
              child: clientesAsync.when(
                loading: () =>
                    const Center(child: CircularProgressIndicator()),
                error: (erro, _) => ListView(
                  children: const [
                    SizedBox(height: 80),
                    Center(
                      child: Text('Não foi possível carregar os clientes.'),
                    ),
                  ],
                ),
                data: (clientes) {
                  final termo = busca.trim().toLowerCase();

                  final filtrados = termo.isEmpty
                      ? clientes
                      : clientes.where((cliente) {
                          return cliente.nome.toLowerCase().contains(termo) ||
                              (cliente.telefone ?? '').contains(termo);
                        }).toList();

                  if (filtrados.isEmpty) {
                    return ListView(
                      children: const [
                        SizedBox(height: 80),
                        Center(child: Text('Nenhum cliente encontrado.')),
                      ],
                    );
                  }

                  return ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: filtrados.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 8),
                    itemBuilder: (context, indice) {
                      final cliente = filtrados[indice];
                      return _CartaoCliente(cliente: cliente);
                    },
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

class _CartaoCliente extends StatelessWidget {
  const _CartaoCliente({required this.cliente});

  final Cliente cliente;

  @override
  Widget build(BuildContext context) {
    final iniciais = cliente.nome.trim().isEmpty
        ? '?'
        : cliente.nome.trim()[0].toUpperCase();

    return Card(
      margin: EdgeInsets.zero,
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(
            builder: (context) => ClienteDetalheScreen(clienteId: cliente.id),
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              CircleAvatar(
                radius: 20,
                backgroundColor: VertexColors.primariaClara,
                child: Text(
                  iniciais,
                  style: const TextStyle(
                    color: VertexColors.primaria,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      cliente.nome,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    if (cliente.telefone != null)
                      Text(
                        cliente.telefone!,
                        style: TextStyle(
                          fontSize: 12.5,
                          color: VertexColors.textoSecundario,
                        ),
                      ),
                  ],
                ),
              ),
              const Icon(
                Icons.chevron_right,
                color: VertexColors.textoTerciario,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
