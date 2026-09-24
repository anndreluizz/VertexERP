import 'package:intl/intl.dart';

final _formatadorMoeda = NumberFormat.currency(locale: 'pt_BR', symbol: 'R\$');

final _formatadorData = DateFormat('dd/MM/yyyy');
final _formatadorDataHora = DateFormat('dd/MM/yyyy HH:mm');

String formatarMoeda(num valor) => _formatadorMoeda.format(valor);

String formatarData(DateTime data) => _formatadorData.format(data);

String formatarDataHora(DateTime data) => _formatadorDataHora.format(data);

/// backend/app/enums/forma_pagamento.py — mesmos valores em texto que
/// o Desktop ja usa.
String formatarFormaPagamento(String? valor) {
  return switch (valor) {
    'DINHEIRO' => 'Dinheiro',
    'PIX' => 'Pix',
    'DEBITO' => 'Débito',
    'CREDITO' => 'Crédito',
    'BOLETO' => 'Boleto',
    'PRAZO' => 'Crediário',
    'TRANSFERENCIA' => 'Transferência',
    'CARTAO' => 'Cartão',
    null => '',
    // valor fora da lista (legado/novo no backend): "CARTAO_X" -> "Cartao x"
    _ =>
      valor.isEmpty
          ? ''
          : valor[0] + valor.substring(1).toLowerCase().replaceAll('_', ' '),
  };
}

const _diasSemana = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom'];
const _meses = [
  'jan',
  'fev',
  'mar',
  'abr',
  'mai',
  'jun',
  'jul',
  'ago',
  'set',
  'out',
  'nov',
  'dez',
];

/// "Hoje", "Ontem" ou "qua, 22 set" -- cabecalho de grupo por dia.
String rotuloDia(DateTime dia, {DateTime? agora}) {
  final ref = agora ?? DateTime.now();
  final hoje = DateTime(ref.year, ref.month, ref.day);
  final d = DateTime(dia.year, dia.month, dia.day);
  final diff = hoje.difference(d).inDays;
  if (diff == 0) return 'Hoje';
  if (diff == 1) return 'Ontem';
  final base = '${_diasSemana[d.weekday - 1]}, ${d.day} ${_meses[d.month - 1]}';
  return d.year == hoje.year ? base : '$base ${d.year}';
}
