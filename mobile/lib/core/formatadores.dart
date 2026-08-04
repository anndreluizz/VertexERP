import 'package:intl/intl.dart';

final _formatadorMoeda = NumberFormat.currency(
  locale: 'pt_BR',
  symbol: 'R\$',
);

String formatarMoeda(num valor) => _formatadorMoeda.format(valor);
