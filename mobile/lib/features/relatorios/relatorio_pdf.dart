import 'dart:typed_data';

import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;

import '../../core/formatadores.dart';
import 'relatorio_dados.dart';

const _corPrimaria = PdfColor.fromInt(0xFF2563EB);
const _corTexto = PdfColor.fromInt(0xFF1E293B);
const _corSecundaria = PdfColor.fromInt(0xFF64748B);

Future<Uint8List> gerarPdfRelatorio({
  required RelatorioDados dados,
  required String nomeLoja,
  required String rotuloPeriodo,
}) async {
  final documento = pw.Document();

  documento.addPage(
    pw.Page(
      pageFormat: PdfPageFormat.a4,
      margin: const pw.EdgeInsets.all(32),
      build: (context) {
        return pw.Column(
          crossAxisAlignment: pw.CrossAxisAlignment.start,
          children: [
            pw.Text(
              nomeLoja,
              style: pw.TextStyle(
                fontSize: 20,
                fontWeight: pw.FontWeight.bold,
                color: _corTexto,
              ),
            ),
            pw.SizedBox(height: 2),
            pw.Text(
              'Relatório gerencial · $rotuloPeriodo',
              style: pw.TextStyle(fontSize: 12, color: _corSecundaria),
            ),
            pw.SizedBox(height: 4),
            pw.Text(
              'Gerado em ${formatarDataHora(DateTime.now())}',
              style: pw.TextStyle(fontSize: 9, color: _corSecundaria),
            ),
            pw.Divider(height: 28, color: _corSecundaria),

            _secao('Vendas'),
            _linha('Quantidade de vendas', '${dados.totalVendas}'),
            _linha('Valor total', formatarMoeda(dados.valorVendas)),
            _linha('Ticket médio', formatarMoeda(dados.ticketMedio)),

            pw.SizedBox(height: 18),
            _secao('Mix de pagamento'),
            if (dados.mixPagamento.isEmpty)
              pw.Text(
                'Nenhuma venda no período.',
                style: pw.TextStyle(color: _corSecundaria, fontSize: 10.5),
              )
            else
              for (final entrada in dados.mixPagamento.entries)
                _linha(
                  formatarFormaPagamento(entrada.key),
                  formatarMoeda(entrada.value),
                ),

            pw.SizedBox(height: 18),
            _secao('Financeiro'),
            _linha(
              'Contas a pagar pendentes',
              formatarMoeda(dados.contasPagarPendente),
            ),
            _linha(
              'Contas a receber pendentes',
              formatarMoeda(dados.contasReceberPendente),
            ),

            pw.SizedBox(height: 18),
            _secao('Estoque'),
            _linha('Produtos em alerta', '${dados.produtosCriticos}'),
            _linha('Produtos sem estoque', '${dados.produtosSemEstoque}'),
          ],
        );
      },
    ),
  );

  return documento.save();
}

pw.Widget _secao(String titulo) {
  return pw.Padding(
    padding: const pw.EdgeInsets.only(bottom: 8),
    child: pw.Text(
      titulo.toUpperCase(),
      style: pw.TextStyle(
        fontSize: 11,
        fontWeight: pw.FontWeight.bold,
        color: _corPrimaria,
        letterSpacing: 0.5,
      ),
    ),
  );
}

pw.Widget _linha(String rotulo, String valor) {
  return pw.Padding(
    padding: const pw.EdgeInsets.symmetric(vertical: 3),
    child: pw.Row(
      mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
      children: [
        pw.Text(rotulo, style: pw.TextStyle(color: _corTexto, fontSize: 11)),
        pw.Text(
          valor,
          style: pw.TextStyle(
            color: _corTexto,
            fontSize: 11,
            fontWeight: pw.FontWeight.bold,
          ),
        ),
      ],
    ),
  );
}
