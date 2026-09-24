import 'package:flutter/material.dart';

/// Varias linhas dentro de um unico card, separadas por divisoria fina
/// -- o jeito "tabela" do Desktop, em vez de um card solto por item.
class ListaAgrupada extends StatelessWidget {
  const ListaAgrupada({super.key, required this.linhas, this.recuo = 16});

  final List<Widget> linhas;

  /// Recuo a esquerda da divisoria (alinha com o texto, nao com a borda).
  final double recuo;

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          for (var i = 0; i < linhas.length; i++) ...[
            if (i > 0) Divider(indent: recuo),
            linhas[i],
          ],
        ],
      ),
    );
  }
}

/// Titulo de grupo acima de uma [ListaAgrupada]: rotulo a esquerda e,
/// opcionalmente, um resumo (total, contagem) a direita.
class CabecalhoGrupo extends StatelessWidget {
  const CabecalhoGrupo(this.titulo, {super.key, this.resumo});

  final String titulo;
  final String? resumo;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;

    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 18, 4, 8),
      child: Row(
        children: [
          Expanded(child: Text(titulo.toUpperCase(), style: tema.labelSmall)),
          if (resumo != null)
            Text(
              resumo!,
              style: tema.labelMedium?.copyWith(
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
        ],
      ),
    );
  }
}
