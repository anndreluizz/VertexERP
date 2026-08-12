import 'package:intl/intl.dart';

final _formatadorMoeda = NumberFormat.currency(
  locale: 'pt_BR',
  symbol: 'R\$',
);

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
    'PRAZO' => 'A prazo',
    _ => valor ?? '',
  };
}
