import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/formatadores.dart';
import 'package:mobile/core/privacidade.dart';
import 'package:mobile/theme/componentes.dart';

void main() {
  testWidgets('olhinho mostra e oculta os valores', (tester) async {
    valoresOcultos.value = true;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Column(
            children: [
              const BotaoOlhoValores(),
              Builder(builder: (_) => Text(moedaTela(1234.5))),
            ],
          ),
        ),
      ),
    );
    expect(find.text(mascaraValor), findsOneWidget);

    await tester.tap(find.byType(BotaoOlhoValores));
    await tester.pump();
    expect(valoresOcultos.value, isFalse);
    expect(find.text(formatarMoeda(1234.5)), findsOneWidget);
    expect(find.byIcon(Icons.visibility_outlined), findsOneWidget);
  });
}
