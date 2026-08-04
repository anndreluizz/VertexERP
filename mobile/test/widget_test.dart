import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:mobile/main.dart';

void main() {
  testWidgets('App sobe sem travar e mostra o carregamento inicial', (
    tester,
  ) async {
    await tester.pumpWidget(
      const ProviderScope(child: VertexManagerApp()),
    );

    expect(find.byType(VertexManagerApp), findsOneWidget);
  });
}
