import 'package:flutter/material.dart';

/// Entrada suave (opacidade + leve deslize de baixo pra cima) --
/// usada pra dar uma sensacao "viva" quando uma lista de cards aparece
/// pela primeira vez, sem precisar de nenhum pacote de animacao.
/// [atraso] escalona cards em sequencia (ver EntradaEscalonada).
class EntradaSuave extends StatelessWidget {
  const EntradaSuave({
    super.key,
    required this.child,
    this.atraso = Duration.zero,
    this.duracao = const Duration(milliseconds: 320),
  });

  final Widget child;
  final Duration atraso;
  final Duration duracao;

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: duracao + atraso,
      curve: Curves.easeOutCubic,
      builder: (context, valor, child) {
        // o atraso vira uma fatia "parada" no comeco da curva, sem
        // precisar de um AnimationController/Timer separado.
        final fracaoAtraso = atraso.inMilliseconds /
            (duracao + atraso).inMilliseconds;
        final progresso = fracaoAtraso >= 1
            ? 0.0
            : ((valor - fracaoAtraso) / (1 - fracaoAtraso)).clamp(0.0, 1.0);

        return Opacity(
          opacity: progresso,
          child: Transform.translate(
            offset: Offset(0, (1 - progresso) * 12),
            child: child,
          ),
        );
      },
      child: child,
    );
  }
}

/// Aplica EntradaSuave num conjunto de widgets, escalonando o atraso
/// de cada um (index * [intervalo]) -- o efeito "cascata" comum em
/// grades/listas de cards.
List<Widget> entradaEscalonada(
  List<Widget> filhos, {
  Duration intervalo = const Duration(milliseconds: 40),
}) {
  return [
    for (var i = 0; i < filhos.length; i++)
      EntradaSuave(atraso: intervalo * i, child: filhos[i]),
  ];
}
