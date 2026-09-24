import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../models/cliente.dart';
import '../../theme/lista_agrupada.dart';
import '../../theme/skeleton.dart';
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
                prefixIcon: Icon(Icons.search_rounded, size: 20),
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
                loading: () => const SkeletonList(),
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

                  // agrupado pela inicial, feito agenda do celular
                  final grupos = <String, List<Cliente>>{};
                  for (final cliente in filtrados) {
                    grupos
                        .putIfAbsent(_letra(cliente.nome), () => [])
                        .add(cliente);
                  }
                  final letras = grupos.keys.toList()..sort();

                  return ListView(
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                    children: [
                      for (final letra in letras) ...[
                        CabecalhoGrupo(letra),
                        ListaAgrupada(
                          recuo: 68,
                          linhas: [
                            for (final cliente in grupos[letra]!)
                              _LinhaCliente(cliente: cliente),
                          ],
                        ),
                      ],
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

String _semAcento(String letra) => switch (letra) {
  'Á' || 'À' || 'Â' || 'Ã' => 'A',
  'É' || 'Ê' => 'E',
  'Í' => 'I',
  'Ó' || 'Ô' || 'Õ' => 'O',
  'Ú' => 'U',
  'Ç' => 'C',
  _ => letra,
};

String _letra(String nome) {
  final limpo = nome.trim();
  if (limpo.isEmpty) return '#';
  final letra = _semAcento(limpo[0].toUpperCase());
  return RegExp('[A-Z]').hasMatch(letra) ? letra : '#';
}

String _iniciais(String nome) {
  final partes = nome.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty);
  if (partes.isEmpty) return '?';
  final primeira = partes.first[0];
  final ultima = partes.length > 1 ? partes.last[0] : '';
  return (primeira + ultima).toUpperCase();
}

class _LinhaCliente extends StatelessWidget {
  const _LinhaCliente({required this.cliente});

  final Cliente cliente;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    final detalhe = [
      cliente.telefone ?? '',
      cliente.cidade ?? '',
    ].where((p) => p.isNotEmpty).join(' · ');

    return InkWell(
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute(
          builder: (context) => ClienteDetalheScreen(clienteId: cliente.id),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            Container(
              width: 38,
              height: 38,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: VertexColors.primariaClara,
                shape: BoxShape.circle,
              ),
              child: Text(
                _iniciais(cliente.nome),
                style: tema.labelMedium?.copyWith(
                  color: VertexColors.escuro
                      ? VertexColors.texto
                      : VertexColors.primaria,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.3,
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
                    style: tema.titleSmall,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (detalhe.isNotEmpty) ...[
                    const SizedBox(height: 2),
                    Text(detalhe, style: tema.bodySmall, maxLines: 1),
                  ],
                ],
              ),
            ),
            Icon(
              Icons.chevron_right_rounded,
              size: 20,
              color: VertexColors.textoTerciario,
            ),
          ],
        ),
      ),
    );
  }
}
