// Renderiza telas em PNG (test_visual/goldens) so pra revisao visual,
// com um "servidor" falso respondendo JSON pronto por rota.
// Rodar: flutter test test_visual --update-goldens
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/api_client.dart';
import 'package:mobile/core/providers.dart';
import 'package:mobile/core/sessao_controller.dart';
import 'package:mobile/features/auth/login_screen.dart';
import 'package:mobile/features/dashboard/dashboard_provider.dart';
import 'package:mobile/features/aprovacoes/aprovacoes_screen.dart';
import 'package:mobile/features/auth/lock_screen.dart';
import 'package:mobile/features/financeiro/comprovante_screen.dart';
import 'package:mobile/features/notificacoes/notificacoes_provider.dart';
import 'package:mobile/features/notificacoes/notificacoes_screen.dart';
import 'package:mobile/features/server/server_setup_screen.dart';
import 'package:mobile/features/caixas/caixas_screen.dart';
import 'package:mobile/features/clientes/cliente_detalhe_screen.dart';
import 'package:mobile/features/estoque/estoque_screen.dart';
import 'package:mobile/features/financeiro/historico_conta_screen.dart';
import 'package:mobile/features/financeiro/realizar_pagamento_screen.dart';
import 'package:mobile/features/relatorios/relatorios_screen.dart';
import 'package:mobile/features/sessoes/sessoes_screen.dart';
import 'package:mobile/features/vendas/venda_detalhe_screen.dart';
import 'package:mobile/home_shell.dart';
import 'package:mobile/models/conta_pagar.dart';
import 'package:mobile/models/venda.dart';
import 'package:mobile/models/dashboard_resumo.dart';
import 'package:mobile/models/usuario.dart';
import 'package:mobile/theme/vertex_colors.dart';
import 'package:mobile/theme/vertex_theme.dart';

Future<void> _fonte(String familia, String caminho) async {
  final bytes = File(caminho).readAsBytesSync();
  await (FontLoader(
    familia,
  )..addFont(Future.value(ByteData.view(bytes.buffer)))).load();
}

final _agora = DateTime.now();
String _d(int diasAtras, [int hora = 10]) => DateTime(
  _agora.year,
  _agora.month,
  _agora.day,
  hora,
).subtract(Duration(days: diasAtras)).toIso8601String();
String _dia(int dias) => _d(-dias).substring(0, 10);

const _nomes = [
  'Maria Aparecida Souza',
  'João Batista Lima',
  'Ana Paula Ferreira',
  'Carlos Eduardo Rocha',
  'Fernanda Oliveira',
  'José Roberto Alves',
  'Luciana Mendes',
  'Paulo Henrique Dias',
];

final _rotas = <String, Object>{
  '/vendas/': [
    for (var i = 0; i < 12; i++)
      {
        'id': 1480 - i,
        'cliente_id': i % 3 == 0 ? null : i,
        'usuario_id': 1,
        'usuario_nome': i.isEven ? 'André' : 'Bia',
        'lucro': 40.0 + i * 7,
        'data': _d(i ~/ 4, 17 - i % 4),
        'valor_total': [89.9, 245.0, 32.5, 1180.0, 54.9, 310.4][i % 6],
        'desconto': 0,
        'observacao': null,
        'status': i == 5 ? 'CANCELADA' : 'FINALIZADA',
        'forma_pagamento': ['PIX', 'DINHEIRO', 'CREDITO', 'PRAZO'][i % 4],
        'itens': [],
      },
  ],
  '/fiado/movimentos': [
    {
      'id': 9,
      'cliente_id': 2,
      'data': _d(0, 11),
      'descricao': null,
      'forma_pagamento': 'PIX',
      'tipo': 'PAGAMENTO',
      'valor': 150.0,
      'venda_id': null,
    },
  ],
  '/clientes/': [
    for (var i = 0; i < _nomes.length; i++)
      {
        'id': i + 1,
        'nome': _nomes[i],
        'ativo': true,
        'cidade': 'Campinas',
        'estado': 'SP',
        'cpf_cnpj': null,
        'criado_em': _d(200),
        'data_nascimento': null,
        'email': null,
        'endereco': null,
        'limite_credito': 500,
        'telefone': '(19) 9 9812-34${10 + i}',
        'tem_foto': false,
      },
  ],
  '/contas-pagar/': [
    for (var i = 0; i < 6; i++)
      {
        'id': i + 1,
        'descricao': [
          'Aluguel da loja',
          'Energia elétrica',
          'Distribuidora Paulista',
          'Internet',
          'Contador',
          'Embalagens',
        ][i],
        'categoria': 'Despesas',
        'data_emissao': _dia(-20),
        'data_pagamento': i == 5 ? _dia(-1) : null,
        'data_vencimento': _dia([-3, 0, 2, 5, 9, -8][i]),
        'status': i == 5 ? 'PAGO' : 'PENDENTE',
        'valor': [2800.0, 412.37, 1935.2, 129.9, 450.0, 280.0][i],
        'banco_pagamento': null,
        'comprovante_pagamento_nome': null,
        'documento_nome': null,
        'forma_pagamento': null,
        'numero_boleto': null,
        'numero_transacao': null,
        'observacao': null,
      },
  ],
  '/contas-receber/': [
    for (var i = 0; i < 5; i++)
      {
        'id': i + 1,
        'cliente_id': i + 1,
        'data_emissao': _dia(-15),
        'data_recebimento': null,
        'data_vencimento': _dia([-2, 0, 4, 10, 15][i]),
        'status': 'PENDENTE',
        'valor': [180.0, 95.5, 420.0, 64.9, 230.0][i],
        'observacao': null,
        'venda_id': 1400 + i,
      },
  ],
  '/aprovacoes/pendentes': [
    {
      'id': 3,
      'tipo': 'CANCELAMENTO_VENDA',
      'descricao': 'Cancelar venda #1475 (R\$ 310,40) — cliente desistiu',
      'referencia_id': 1475,
      'solicitante_id': 2,
      'status': 'PENDENTE',
      'criado_em': _d(0, 14),
    },
    {
      'id': 4,
      'tipo': 'CANCELAMENTO_CONTA_PAGAR',
      'descricao': 'Cancelar despesa "Embalagens" já paga',
      'referencia_id': 6,
      'solicitante_id': 2,
      'status': 'PENDENTE',
      'criado_em': _d(1, 16),
    },
  ],
  '/configuracoes': {},
  '/notificacoes/nao-lidas': {'nao_lidas': 3},
  '/notificacoes/': [
    for (final (i, t, c, h, lida) in [
      (
        6,
        'Venda no fiado',
        'Venda #1481 — R\$ 245,00 (Maria Aparecida Souza)',
        0,
        false,
      ),
      (
        5,
        'Recebimento de fiado',
        'João Batista Lima pagou R\$ 150,00. Saldo devedor: R\$ 95,50.',
        1,
        false,
      ),
      (4, 'Nova venda', 'Venda #1480 — R\$ 89,90', 2, false),
      (
        3,
        'Conta recebida',
        'Ana Paula Ferreira — R\$ 180,00 (conta Nº 12).',
        5,
        true,
      ),
      (
        2,
        'Cliente inadimplente',
        'Carlos Eduardo Rocha passou do limite de crédito (R\$ 612,00 de R\$ 500,00).',
        26,
        true,
      ),
      (
        1,
        'Haver lançado',
        'Luciana Mendes recebeu um haver de R\$ 20,00. Saldo devedor: R\$ 0,00.',
        28,
        true,
      ),
    ])
      {
        'id': i,
        'titulo': t,
        'corpo': c,
        'lida': lida,
        'criado_em': DateTime.now()
            .toUtc()
            .subtract(Duration(hours: h))
            .toIso8601String()
            .replaceAll('Z', ''),
      },
  ],
  '/produtos/': [
    for (var i = 0; i < 10; i++)
      {
        'id': i + 1,
        'codigo': 'P${(1000 + i)}',
        'nome': [
          'Arroz Tio João 5kg',
          'Feijão Carioca Camil 1kg',
          'Óleo de Soja Liza 900ml',
          'Café Pilão 500g',
          'Açúcar União 1kg',
          'Leite Integral Italac 1L',
          'Detergente Ypê 500ml',
          'Sabão em Pó Omo 1,6kg',
          'Macarrão Renata 500g',
          'Biscoito Maizena 400g',
        ][i],
        'categoria': i < 6 ? 'Mercearia' : 'Limpeza',
        'estoque': [0, 3, 12, 0, 40, 5, 22, 1, 60, 8][i],
        'estoque_minimo': [10, 10, 8, 5, 10, 12, 10, 6, 10, 10][i],
        'preco_venda': [
          29.9,
          8.49,
          7.99,
          18.9,
          4.99,
          5.49,
          2.79,
          32.9,
          4.29,
          5.99,
        ][i],
        'ativo': true,
      },
  ],
  '/caixa/historico': [
    for (var i = 0; i < 5; i++)
      {
        'id': 60 - i,
        'usuario_id': i.isEven ? 1 : 2,
        'data_abertura': _d(i, 8),
        'data_fechamento': i == 0 ? null : _d(i, 19),
        'saldo_inicial': 200.0,
        'saldo_final': 1840.5 + i * 97,
        'status': i == 0 ? 'ABERTO' : 'FECHADO',
      },
  ],
  '/users/': {
    'data': [
      {
        'id': 1,
        'nome': 'André Lopes',
        'email': 'a@v.com',
        'ativo': true,
        'admin': true,
      },
      {
        'id': 2,
        'nome': 'Bia Santos',
        'email': 'b@v.com',
        'ativo': true,
        'admin': false,
      },
    ],
  },
  '/auth/sessoes': [
    {
      'id': 1,
      'dispositivo': 'Samsung Galaxy A54',
      'criado_em': _d(12),
      'ultimo_uso_em': _d(0, 15),
    },
    {
      'id': 2,
      'dispositivo': 'Windows — Caixa 1',
      'criado_em': _d(40),
      'ultimo_uso_em': _d(1, 18),
    },
  ],
};

Object? _responder(String path) {
  if (_rotas.containsKey(path)) return _rotas[path];
  if (path == '/contas-pagar/pendentes') return _rotas['/contas-pagar/'];
  if (path == '/contas-receber/pendentes') return _rotas['/contas-receber/'];
  if (RegExp(r'^/clientes/\d+$').hasMatch(path)) {
    return (_rotas['/clientes/']! as List).first;
  }
  if (path.startsWith('/fiado/saldo/')) return {'saldo': 320.5};
  if (path.startsWith('/fiado/movimentos/cliente/')) {
    return [
      for (var i = 0; i < 5; i++)
        {
          'id': 20 + i,
          'cliente_id': 1,
          'data': _d(i * 6, 11),
          'descricao': i.isOdd ? null : 'Venda #${1400 + i}',
          'forma_pagamento': i.isOdd ? 'PIX' : null,
          'tipo': i.isOdd ? 'PAGAMENTO' : 'COMPRA',
          'valor': [180.0, 100.0, 95.5, 50.0, 194.99][i],
          'venda_id': i.isOdd ? null : 1400 + i,
        },
    ];
  }
  if (RegExp(r'^/contas-pagar/\d+/eventos$').hasMatch(path)) {
    return [
      {
        'id': 1,
        'tipo': 'CRIADA',
        'data': _d(20, 9),
        'usuario_nome': 'André',
        'dispositivo': 'Desktop',
        'detalhes': null,
      },
      {
        'id': 2,
        'tipo': 'DOCUMENTO_ANEXADO',
        'data': _d(20, 9),
        'usuario_nome': 'André',
        'dispositivo': 'Desktop',
        'detalhes': 'boleto.pdf',
      },
      {
        'id': 3,
        'tipo': 'PAGA',
        'data': _d(1, 16),
        'usuario_nome': 'Bia',
        'dispositivo': 'Celular',
        'detalhes': 'Pix',
      },
    ];
  }
  return null;
}

ApiClient _apiFalsa() {
  final api = ApiClient();
  api.dio.interceptors.insert(
    0,
    InterceptorsWrapper(
      onRequest: (o, h) {
        final corpo =
            _responder(o.path) ?? (o.path.endsWith('/') ? <Object>[] : {});
        h.resolve(Response(requestOptions: o, statusCode: 200, data: corpo));
      },
    ),
  );
  return api;
}

final _resumo = DashboardResumo.fromJson({
  'vendas_hoje': 3847.9,
  'vendas_hoje_qtd': 27,
  'vendas_mes': 68420.5,
  'compras_hoje': 1200,
  'saldo_caixa': 2154.3,
  'contas_receber': 9830.0,
  'contas_pagar': 5412.75,
  'clientes': 342,
  'fornecedores': 18,
  'produtos': 1287,
  'estoque_baixo': 12,
  'contas_vencidas_qtd': 3,
  'contas_vencidas_valor': 870.0,
  'contas_vencendo_hoje_qtd': 2,
  'contas_vencendo_hoje_valor': 450.0,
  'contas_pagas_hoje_qtd': 4,
  'contas_pagas_hoje_valor': 1320.0,
  'fiado_recebido_hoje': 210.0,
  'contas_mes_pago': 12400,
  'contas_mes_pendente': 5412.75,
  'serie_recebimentos_mensal': [
    for (var m = 4; m <= 9; m++)
      {'mes': '2026-0$m', 'valor': 30000.0 + m * 4100 % 9000},
  ],
  'serie_pagamentos_mensal': [
    for (var m = 4; m <= 9; m++)
      {'mes': '2026-0$m', 'valor': 18000.0 + m * 2700 % 7000},
  ],
});

Future<void> _render(
  WidgetTester t,
  Widget tela,
  String nome,
  bool escuro, {
  int aba = 0,
}) async {
  t.view.physicalSize = const Size(1080, 2340);
  t.view.devicePixelRatio = 2.75;
  VertexColors.aplicar(escuro: escuro);
  final container = ProviderContainer(
    overrides: [
      apiClientProvider.overrideWithValue(_apiFalsa()),
      abaSelecionadaProvider.overrideWith((ref) => aba),
      vigiaNotificacoesProvider.overrideWith(_VigiaSemPlugin.new),
      dashboardProvider.overrideWith(
        (ref) async => DashboardCarregado(
          resumo: _resumo,
          deCache: false,
          atualizadoEm: DateTime(2026, 9, 23, 15, 40),
        ),
      ),
    ],
  );
  await t.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: escuro ? VertexTheme.escuro : VertexTheme.claro,
        home: tela,
      ),
    ),
  );
  await t.pump();
  // ignore: invalid_use_of_protected_member, invalid_use_of_visible_for_testing_member
  container.read(sessaoControllerProvider.notifier).state = const SessaoState(
    status: StatusSessao.logado,
    nomeLoja: 'Filial Centro',
    usuario: Usuario(
      id: 1,
      nome: 'André Lopes',
      email: 'andre@vertex.com',
      ativo: true,
      admin: true,
    ),
  );
  for (var i = 0; i < 20; i++) {
    await t.pump(const Duration(milliseconds: 100));
  }
  await expectLater(
    find.byType(MaterialApp),
    matchesGoldenFile('goldens/${nome}_${escuro ? 'escuro' : 'claro'}.png'),
  );
}

void main() {
  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized().defaultBinaryMessenger
        .setMockMethodCallHandler(
          const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
          (_) async => null,
        );
    await _fonte('Inter', 'assets/fonts/Inter-Variable.ttf');
    await _fonte(
      'MaterialIcons',
      'C:/src/flutter/bin/cache/dart-sdk/bin/resources/devtools/assets/fonts/MaterialIcons-Regular.otf',
    );
  });

  const abas = ['inicio', 'vendas', 'clientes', 'financeiro', 'mais'];

  final venda = Venda.fromJson({
    ...((_rotas['/vendas/']! as List).first as Map<String, dynamic>),
    'cliente_id': 1,
    'desconto': 5.0,
    'itens': [
      {
        'id': 1,
        'produto_id': 1,
        'quantidade': 2,
        'valor_unitario': 29.9,
        'subtotal': 59.8,
      },
      {
        'id': 2,
        'produto_id': 4,
        'quantidade': 1,
        'valor_unitario': 18.9,
        'subtotal': 18.9,
      },
      {
        'id': 3,
        'produto_id': 7,
        'quantidade': 6,
        'valor_unitario': 2.79,
        'subtotal': 16.74,
      },
    ],
  });
  final contas = (_rotas['/contas-pagar/']! as List)
      .map((j) => ContaPagar.fromJson(j as Map<String, dynamic>))
      .toList();
  final internas = <String, Widget Function()>{
    'cliente_detalhe': () => const ClienteDetalheScreen(clienteId: 1),
    'venda_detalhe': () => VendaDetalheScreen(venda: venda),
    'estoque': () => const EstoqueScreen(),
    'caixas': () => const CaixasScreen(),
    'relatorios': () => const RelatoriosScreen(),
    'sessoes': () => const SessoesScreen(),
    'aprovacoes': () => const AprovacoesScreen(),
    'pagamento': () => RealizarPagamentoScreen(conta: contas[1]),
    'historico_conta': () => HistoricoContaScreen(conta: contas[5]),
    'bloqueio': () => const LockScreen(),
    'servidor': () => const ServerSetupScreen(),
    'notificacoes': () => const NotificacoesScreen(),
    'comprovante': () => ComprovanteScreen(conta: contas[5]),
  };
  for (final escuro in [false, true]) {
    for (final MapEntry(key: nome, value: tela) in internas.entries) {
      testWidgets('$nome $escuro', (t) => _render(t, tela(), nome, escuro));
    }
  }
  for (final escuro in [false, true]) {
    testWidgets(
      'login $escuro',
      (t) => _render(t, const LoginScreen(), 'login', escuro),
    );
    for (var i = 0; i < abas.length; i++) {
      testWidgets(
        '${abas[i]} $escuro',
        (t) => _render(t, const HomeShell(), abas[i], escuro, aba: i),
      );
    }
  }
}

/// Plugin de notificacao do Android nao existe no teste -- so consulta
/// o servidor (atualiza o contador), sem mostrar na barra.
class _VigiaSemPlugin extends VigiaNotificacoes {
  _VigiaSemPlugin(super.ref);

  @override
  Future<void> iniciar() => verificar();
}
