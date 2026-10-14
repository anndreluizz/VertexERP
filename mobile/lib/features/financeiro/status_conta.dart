import 'package:flutter/material.dart';

import '../../models/conta_pagar.dart';
import '../../theme/vertex_colors.dart';

/// Classificacao visual de uma conta a pagar -- cruza o status
/// gravado no banco (PENDENTE/PAGO/CANCELADO) com a data de
/// vencimento pra decidir o rotulo/cor certos (mesmo criterio usado
/// no Desktop, so que aqui vira um valor nomeado em vez de so cor).
enum StatusVisualConta { paga, vencida, venceHoje, aVencer, cancelada }

extension StatusVisualContaInfo on StatusVisualConta {
  String get rotulo => switch (this) {
    StatusVisualConta.paga => 'Paga',
    StatusVisualConta.vencida => 'Vencida',
    StatusVisualConta.venceHoje => 'Vence hoje',
    StatusVisualConta.aVencer => 'A vencer',
    StatusVisualConta.cancelada => 'Cancelada',
  };

  String get rotuloGrupo => switch (this) {
    StatusVisualConta.paga => 'Pagas',
    StatusVisualConta.vencida => 'Vencidas',
    StatusVisualConta.venceHoje => 'Vence hoje',
    StatusVisualConta.aVencer => 'A vencer',
    StatusVisualConta.cancelada => 'Canceladas',
  };

  Color get cor => switch (this) {
    StatusVisualConta.paga => VertexColors.secundaria,
    StatusVisualConta.vencida => VertexColors.erro,
    StatusVisualConta.venceHoje => VertexColors.alerta,
    StatusVisualConta.aVencer => VertexColors.primaria,
    StatusVisualConta.cancelada => VertexColors.textoTerciario,
  };

  Color get corFundo => switch (this) {
    StatusVisualConta.paga => VertexColors.sucessoClaro,
    StatusVisualConta.vencida => VertexColors.erroClaro,
    StatusVisualConta.venceHoje => VertexColors.alertaClaro,
    StatusVisualConta.aVencer => VertexColors.primariaClara,
    StatusVisualConta.cancelada => VertexColors.fundo,
  };
}

StatusVisualConta statusVisual(ContaPagar conta) {
  if (conta.status == 'CANCELADO') return StatusVisualConta.cancelada;
  if (conta.status == 'PAGO') return StatusVisualConta.paga;
  return _porVencimento(conta.dataVencimento);
}

StatusVisualConta _porVencimento(DateTime vencimento) {
  final hoje = DateTime.now();
  final diasParaVencer = DateTime(
    vencimento.year,
    vencimento.month,
    vencimento.day,
  ).difference(DateTime(hoje.year, hoje.month, hoje.day)).inDays;

  if (diasParaVencer < 0) return StatusVisualConta.vencida;
  if (diasParaVencer == 0) return StatusVisualConta.venceHoje;
  return StatusVisualConta.aVencer;
}

/// Pilula colorida de status -- usada no cartao da lista.
class StatusContaPill extends StatelessWidget {
  const StatusContaPill({super.key, required this.status});

  final StatusVisualConta status;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
      decoration: BoxDecoration(
        color: status.corFundo,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        status.rotulo,
        style: TextStyle(
          fontSize: 10.5,
          fontWeight: FontWeight.w700,
          color: status.cor,
        ),
      ),
    );
  }
}
