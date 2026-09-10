// Testa o fluxo de 2FA do SessaoController (login() devolvendo
// verificacaoId + verificarCodigo2fa()) contra um servidor HTTPS real
// de teste -- mesmo servidor de teste do fluxo TOFU
// (fixtures/servidor_teste.py / fixtures/servidor_teste.dart), que já
// implementa /auth/login, /auth/verificar-2fa, /auth/me e
// /configuracoes. Conecta via https:// (o servidor só fala HTTPS) --
// o primeiro contato confia sozinho no certificado autoassinado, via
// o mesmo mecanismo TOFU do ApiClient (ver tofu_desktop_paridade_test.dart).
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/api_client.dart';
import 'package:mobile/core/sessao_controller.dart';
import 'package:mobile/core/vertex_storage.dart';

import 'fixtures/servidor_teste.dart';

const _porta = 58798;

/// Mock em memoria do canal de plataforma do flutter_secure_storage --
/// mesmo usado em tofu_desktop_paridade_test.dart.
class _ArmazenamentoFalso {
  final Map<String, String> _dados = {};

  void instalar() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
          const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
          (chamada) async {
            switch (chamada.method) {
              case 'write':
                _dados[chamada.arguments['key'] as String] =
                    chamada.arguments['value'] as String;
                return null;
              case 'read':
                return _dados[chamada.arguments['key'] as String];
              case 'delete':
                _dados.remove(chamada.arguments['key'] as String);
                return null;
              case 'readAll':
                return _dados;
              case 'deleteAll':
                _dados.clear();
                return null;
              case 'containsKey':
                return _dados.containsKey(chamada.arguments['key'] as String);
              default:
                return null;
            }
          },
        );
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  HttpOverrides.global = null;

  late ServidorTeste servidor;

  setUpAll(() async {
    servidor = await ServidorTeste.subir(_porta);
  });

  tearDownAll(() async {
    await servidor.derrubar();
  });

  test('login sem 2FA continua funcionando normalmente', () async {
    _ArmazenamentoFalso().instalar();

    final controller = SessaoController(ApiClient(), VertexStorage());
    await controller.configurarServidor('https://127.0.0.1:$_porta');

    final resultado = await controller.login(
      'teste@vertex.com',
      'sem2fa',
      lembrar: false,
    );

    expect(resultado.sucesso, isTrue);
    expect(resultado.erro, isNull);
    expect(resultado.verificacaoId, isNull);
    expect(controller.state.status, StatusSessao.logado);
    expect(controller.state.usuario?.nome, 'Usuario Teste');
  });

  test('login com 2FA ativo devolve verificacaoId, sem logar ainda', () async {
    _ArmazenamentoFalso().instalar();

    final controller = SessaoController(ApiClient(), VertexStorage());
    await controller.configurarServidor('https://127.0.0.1:$_porta');

    final resultado = await controller.login(
      'teste@vertex.com',
      'com2fa',
      lembrar: false,
    );

    expect(resultado.sucesso, isFalse);
    expect(resultado.verificacaoId, 'verif-teste-123');
    expect(controller.state.status, isNot(StatusSessao.logado));
  });

  test('verificarCodigo2fa com codigo certo completa o login', () async {
    _ArmazenamentoFalso().instalar();

    final controller = SessaoController(ApiClient(), VertexStorage());
    await controller.configurarServidor('https://127.0.0.1:$_porta');

    final primeiroPasso = await controller.login(
      'teste@vertex.com',
      'com2fa',
      lembrar: false,
    );

    final erro = await controller.verificarCodigo2fa(
      primeiroPasso.verificacaoId!,
      '654321',
      lembrar: false,
    );

    expect(erro, isNull);
    expect(controller.state.status, StatusSessao.logado);
  });

  test('verificarCodigo2fa com codigo errado nao loga', () async {
    _ArmazenamentoFalso().instalar();

    final controller = SessaoController(ApiClient(), VertexStorage());
    await controller.configurarServidor('https://127.0.0.1:$_porta');

    final primeiroPasso = await controller.login(
      'teste@vertex.com',
      'com2fa',
      lembrar: false,
    );

    final erro = await controller.verificarCodigo2fa(
      primeiroPasso.verificacaoId!,
      '000000',
      lembrar: false,
    );

    expect(erro, isNotNull);
    expect(controller.state.status, isNot(StatusSessao.logado));
  });
}
