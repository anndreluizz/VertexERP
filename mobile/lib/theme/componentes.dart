import 'package:flutter/material.dart';

import '../core/cliente_analise.dart';
import '../core/privacidade.dart';
import 'vertex_colors.dart';
import 'vertex_theme.dart';

/// Pecas visuais do redesign (prototipo aprovado em 07/10) usadas por
/// mais de uma tela: selo colorido, avatar de iniciais, barra de uso do
/// limite, chip de filtro e cabecalho de tela.

const tabular = [FontFeature.tabularFigures()];

/// (fundo, texto/icone, barra) de cada situacao do cliente.
(Color, Color, Color) coresStatusCliente(StatusCliente status) =>
    switch (status) {
      StatusCliente.inadimplente => (
        VertexColors.erroClaro,
        VertexColors.erro,
        VertexColors.erro,
      ),
      StatusCliente.pagaComAtraso => (
        VertexColors.alertaClaro,
        VertexColors.alertaTexto,
        VertexColors.alerta,
      ),
      StatusCliente.bomPagador => (
        VertexColors.sucessoClaro,
        VertexColors.escuro ? VertexColors.sucesso : const Color(0xFF0F6E57),
        VertexColors.sucesso,
      ),
      StatusCliente.emDia => (
        VertexColors.primariaClara,
        VertexColors.escuro ? VertexColors.texto : VertexColors.primaria,
        VertexColors.primaria,
      ),
      StatusCliente.quitado => (
        VertexColors.fundo,
        VertexColors.textoSecundario,
        VertexColors.bordaForte,
      ),
    };

String iniciais(String nome) {
  final partes = nome
      .replaceAll(RegExp(r'[()]'), ' ')
      .trim()
      .split(RegExp(r'\s+'))
      .where((p) => p.isNotEmpty)
      .toList();
  if (partes.isEmpty) return '?';
  final segunda = partes.length > 1 ? partes[1][0] : '';
  return (partes.first[0] + segunda).toUpperCase();
}

class Selo extends StatelessWidget {
  const Selo(
    this.texto, {
    super.key,
    required this.fundo,
    required this.cor,
    this.icone,
  });

  final String texto;
  final Color fundo;
  final Color cor;
  final IconData? icone;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: fundo,
        borderRadius: BorderRadius.circular(99),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icone != null) ...[
            Icon(icone, size: 13, color: cor),
            const SizedBox(width: 3),
          ],
          Text(
            texto,
            style: TextStyle(
              fontSize: 11.5,
              fontWeight: FontWeight.w700,
              color: cor,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }
}

class SeloStatusCliente extends StatelessWidget {
  const SeloStatusCliente(this.status, {super.key});

  final StatusCliente status;

  @override
  Widget build(BuildContext context) {
    final (fundo, cor, _) = coresStatusCliente(status);
    return Selo(
      status.rotulo,
      fundo: fundo,
      cor: cor,
      icone: status == StatusCliente.bomPagador ? Icons.star_rounded : null,
    );
  }
}

class AvatarIniciais extends StatelessWidget {
  const AvatarIniciais({
    super.key,
    required this.nome,
    required this.fundo,
    required this.cor,
    this.tamanho = 42,
  });

  final String nome;
  final Color fundo;
  final Color cor;
  final double tamanho;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: tamanho,
      height: tamanho,
      alignment: Alignment.center,
      decoration: BoxDecoration(color: fundo, shape: BoxShape.circle),
      child: Text(
        iniciais(nome),
        style: TextStyle(
          fontWeight: FontWeight.w700,
          fontSize: tamanho * 0.34,
          color: cor,
        ),
      ),
    );
  }
}

/// Barra fina de progresso (uso do limite, divisao do fiado...).
class BarraProgresso extends StatelessWidget {
  const BarraProgresso({
    super.key,
    required this.fracao,
    required this.cor,
    this.fundo,
    this.altura = 5,
  });

  final double fracao;
  final Color cor;
  final Color? fundo;
  final double altura;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(altura),
      child: SizedBox(
        height: altura,
        child: Stack(
          fit: StackFit.expand,
          children: [
            ColoredBox(color: fundo ?? VertexColors.fundo),
            FractionallySizedBox(
              alignment: Alignment.centerLeft,
              widthFactor: fracao.clamp(0.0, 1.0),
              child: ColoredBox(color: cor),
            ),
          ],
        ),
      ),
    );
  }
}

/// Chip de filtro: escuro quando ligado, contornado quando nao.
class ChipFiltro extends StatelessWidget {
  const ChipFiltro({
    super.key,
    required this.rotulo,
    required this.ligado,
    required this.aoTocar,
  });

  final String rotulo;
  final bool ligado;
  final VoidCallback aoTocar;

  @override
  Widget build(BuildContext context) {
    final fundo = ligado ? VertexColors.texto : VertexColors.card;
    return Semantics(
      selected: ligado,
      button: true,
      child: Material(
        color: fundo,
        shape: StadiumBorder(
          side: BorderSide(color: ligado ? fundo : VertexColors.borda),
        ),
        child: InkWell(
          customBorder: const StadiumBorder(),
          onTap: aoTocar,
          child: Container(
            height: 36,
            padding: const EdgeInsets.symmetric(horizontal: 14),
            alignment: Alignment.center,
            child: Text(
              rotulo,
              style: TextStyle(
                fontSize: 13.5,
                fontWeight: FontWeight.w600,
                color: ligado
                    ? VertexColors.fundo
                    : VertexColors.textoSecundario,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Titulo grande da aba (Bricolage) + linha de resumo embaixo.
class CabecalhoTela extends StatelessWidget {
  const CabecalhoTela({
    super.key,
    required this.titulo,
    this.subtitulo,
    this.acao,
  });

  final String titulo;
  final String? subtitulo;
  final Widget? acao;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 16, 12),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  titulo,
                  style: const TextStyle(
                    fontFamily: VertexTheme.fonteDisplay,
                    fontSize: 26,
                    fontWeight: FontWeight.w700,
                    height: 1.15,
                  ).copyWith(color: VertexColors.texto),
                ),
                if (subtitulo != null)
                  Text(
                    subtitulo!,
                    style: TextStyle(
                      fontSize: 13,
                      color: VertexColors.textoSecundario,
                      fontFeatures: tabular,
                    ),
                  ),
              ],
            ),
          ),
          const BotaoOlhoValores(),
          ?acao,
        ],
      ),
    );
  }
}

/// Olhinho que mostra/oculta os valores em dinheiro (core/privacidade).
class BotaoOlhoValores extends StatelessWidget {
  const BotaoOlhoValores({super.key, this.cor, this.compacto = false});

  final Color? cor;

  /// Menor, pra ficar colado no titulo de um card.
  final bool compacto;

  @override
  Widget build(BuildContext context) {
    final ocultos = valoresOcultos.value;
    return IconButton(
      tooltip: ocultos ? 'Mostrar valores' : 'Ocultar valores',
      onPressed: alternarValoresOcultos,
      visualDensity: compacto ? VisualDensity.compact : null,
      iconSize: compacto ? 20 : null,
      icon: Icon(
        ocultos ? Icons.visibility_off_outlined : Icons.visibility_outlined,
        color: cor ?? VertexColors.textoSecundario,
      ),
    );
  }
}

/// Botao quadrado 44x44 com icone (ordenar, buscar, voltar...).
class BotaoIcone extends StatelessWidget {
  const BotaoIcone({
    super.key,
    required this.icone,
    required this.dica,
    required this.aoTocar,
  });

  final IconData icone;
  final String dica;
  final VoidCallback? aoTocar;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: dica,
      child: Material(
        color: VertexColors.card,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: VertexColors.borda),
        ),
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: aoTocar,
          child: SizedBox(
            width: 44,
            height: 44,
            child: Icon(icone, size: 20, color: VertexColors.texto),
          ),
        ),
      ),
    );
  }
}

/// Titulo de secao dentro da tela ("Precisa da sua atencao").
class TituloSecao extends StatelessWidget {
  const TituloSecao(this.texto, {super.key, this.resumo});

  final String texto;
  final String? resumo;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.baseline,
        textBaseline: TextBaseline.alphabetic,
        children: [
          Expanded(
            child: Text(
              texto,
              style: TextStyle(
                fontFamily: VertexTheme.fonteDisplay,
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: VertexColors.texto,
              ),
            ),
          ),
          if (resumo != null)
            Text(
              resumo!,
              style: TextStyle(
                fontSize: 13,
                color: VertexColors.textoSecundario,
              ),
            ),
        ],
      ),
    );
  }
}
