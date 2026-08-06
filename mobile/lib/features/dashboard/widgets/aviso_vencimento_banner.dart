import 'package:flutter/material.dart';

import '../../../core/formatadores.dart';
import '../../../theme/vertex_colors.dart';

/// Banner de alerta no topo do dashboard quando ha conta(s) vencida(s)
/// ou vencendo hoje -- o gatilho que puxa a atencao do gerente antes
/// mesmo de ele abrir o Financeiro. Toque leva direto pra la.
class AvisoVencimentoBanner extends StatelessWidget {
  const AvisoVencimentoBanner({
    super.key,
    required this.vencidasQtd,
    required this.vencidasValor,
    required this.vencendoHojeQtd,
    required this.vencendoHojeValor,
    required this.aoTocar,
  });

  final int vencidasQtd;
  final double vencidasValor;
  final int vencendoHojeQtd;
  final double vencendoHojeValor;
  final VoidCallback aoTocar;

  @override
  Widget build(BuildContext context) {
    final total = vencidasQtd + vencendoHojeQtd;
    if (total == 0) return const SizedBox.shrink();

    // vencida pesa mais que "vence hoje" -- se tiver as duas, o tom do
    // banner e o mais serio dos dois.
    final grave = vencidasQtd > 0;
    final cor = grave ? VertexColors.erro : VertexColors.alerta;
    final corFundo = grave ? VertexColors.erroClaro : VertexColors.alertaClaro;

    final partes = <String>[];
    if (vencidasQtd > 0) {
      partes.add(
        '$vencidasQtd vencida${vencidasQtd > 1 ? 's' : ''} '
        '(${formatarMoeda(vencidasValor)})',
      );
    }
    if (vencendoHojeQtd > 0) {
      partes.add(
        '$vencendoHojeQtd vencendo hoje '
        '(${formatarMoeda(vencendoHojeValor)})',
      );
    }

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: aoTocar,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          margin: const EdgeInsets.fromLTRB(20, 0, 20, 4),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            color: corFundo,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: cor.withValues(alpha: 0.25)),
          ),
          child: Row(
            children: [
              Icon(Icons.warning_amber_rounded, size: 20, color: cor),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  partes.join(' · '),
                  style: TextStyle(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w600,
                    color: cor,
                  ),
                ),
              ),
              Icon(Icons.chevron_right, size: 18, color: cor),
            ],
          ),
        ),
      ),
    );
  }
}
