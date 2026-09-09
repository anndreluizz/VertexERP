// Verifica o fluxo TOFU (trust on first use) do ApiClient contra um
// servidor HTTPS real (o mesmo backend de teste usado na verificação
// equivalente do Desktop) -- primeiro contato confia sozinho, segunda
// chamada reusa o pin, e um certificado trocado se comporta diferente
// em host local (127.0.0.1, reconfia sozinho) vs host "remoto"
// (127.0.0.2 -- endereço de loopback real do Windows, mas fora da
// lista eh_endereco_local, dá pra simular "outra máquina" sem
// precisar de uma de verdade).
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/api_client.dart';
import 'package:mobile/core/tls_confianca.dart';

const _pythonExe = 'C:/vtest/venv/Scripts/python.exe';
const _servidorScript =
    'C:/Users/lopes/AppData/Local/Temp/claude/'
    'C--projetos-VertexERP--claude-worktrees-project-status-check-81f1b7/'
    '6e962d8b-57fe-4c60-b96f-157fdfa99edb/scratchpad/'
    'servidor_teste_tls_desktop.py';

const _cert1 =
    'C:/Users/lopes/AppData/Local/Temp/claude/'
    'C--projetos-VertexERP--claude-worktrees-project-status-check-81f1b7/'
    '6e962d8b-57fe-4c60-b96f-157fdfa99edb/scratchpad/'
    'certs_mobile_teste_1/servidor.crt';
const _chave1 =
    'C:/Users/lopes/AppData/Local/Temp/claude/'
    'C--projetos-VertexERP--claude-worktrees-project-status-check-81f1b7/'
    '6e962d8b-57fe-4c60-b96f-157fdfa99edb/scratchpad/'
    'certs_mobile_teste_1/servidor.key';
const _cert2 =
    'C:/Users/lopes/AppData/Local/Temp/claude/'
    'C--projetos-VertexERP--claude-worktrees-project-status-check-81f1b7/'
    '6e962d8b-57fe-4c60-b96f-157fdfa99edb/scratchpad/'
    'certs_mobile_teste_2/servidor.crt';
const _chave2 =
    'C:/Users/lopes/AppData/Local/Temp/claude/'
    'C--projetos-VertexERP--claude-worktrees-project-status-check-81f1b7/'
    '6e962d8b-57fe-4c60-b96f-157fdfa99edb/scratchpad/'
    'certs_mobile_teste_2/servidor.key';

const _porta = 58797;

/// Mock em memória do canal de plataforma do flutter_secure_storage --
/// em "flutter test" (VM pura, sem device de verdade) não existe uma
/// implementação nativa real do outro lado do MethodChannel.
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

Future<Process> _subirServidor(String cert, String chave, int porta) async {
  final processo = await Process.start(_pythonExe, [
    _servidorScript,
    cert,
    chave,
    porta.toString(),
  ]);

  // espera a porta responder de verdade antes de seguir
  for (var i = 0; i < 50; i++) {
    try {
      final socket = await Socket.connect(
        '127.0.0.1',
        porta,
        timeout: const Duration(milliseconds: 300),
      );
      await socket.close();
      return processo;
    } catch (_) {
      await Future.delayed(const Duration(milliseconds: 200));
    }
  }

  throw StateError('servidor de teste não subiu a tempo');
}

Future<void> _derrubarServidor(Process processo, int porta) async {
  processo.kill();
  await processo.exitCode;

  for (var i = 0; i < 30; i++) {
    try {
      final socket = await Socket.connect(
        '127.0.0.1',
        porta,
        timeout: const Duration(milliseconds: 200),
      );
      await socket.close();
      await Future.delayed(const Duration(milliseconds: 200));
    } catch (_) {
      return; // porta livre
    }
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  // TestWidgetsFlutterBinding troca o HttpOverrides global por um que
  // devolve 400 sem fazer nenhuma chamada de rede de verdade (proteção
  // padrão do flutter_test contra teste bater na rede sem querer) --
  // esse teste especificamente PRECISA de rede real (contra o
  // servidor de teste local), entao desliga esse override.
  HttpOverrides.global = null;

  test(
    'fluxo TOFU completo contra servidor HTTPS real',
    () async {
      _ArmazenamentoFalso().instalar();

      Process? processo;

      try {
        // -----------------------------------------------------------
        // 1) primeiro contato (127.0.0.1, genuinamente local) --
        // confia sozinho, sem pin previo
        // -----------------------------------------------------------

        processo = await _subirServidor(_cert1, _chave1, _porta);

        final api = ApiClient();

        final ok1 = await api.testarConexao('127.0.0.1:$_porta');
        expect(ok1, isTrue, reason: 'primeiro contato deveria conectar');
        expect(api.ultimaFalhaCertificado, isNull);

        // -----------------------------------------------------------
        // 2) segunda chamada -- usa o pin salvo, continua funcionando
        // -----------------------------------------------------------

        final ok2 = await api.testarConexao('127.0.0.1:$_porta');
        expect(
          ok2,
          isTrue,
          reason: 'segunda chamada (com pin) deveria continuar funcionando',
        );

        // -----------------------------------------------------------
        // 3) "servidor reinstalado": derruba, sobe de novo com outro
        // certificado na MESMA porta, mas em 127.0.0.2 -- endereço de
        // loopback real do Windows, então da pra conectar de verdade,
        // só que TlsConfianca.ehEnderecoLocal não reconhece como
        // "local" (só 127.0.0.1/localhost/::1) -- simula "servidor
        // numa rede remota" sem precisar de uma segunda máquina.
        // -----------------------------------------------------------

        await _derrubarServidor(processo, _porta);

        processo = await _subirServidor(_cert2, _chave2, _porta);

        final apiRemoto = ApiClient();
        // primeiro contato em "127.0.0.2" -- TOFU confia no cert2 (é
        // a primeira vez que esse host:porta é visto)
        final okRemoto1 = await apiRemoto.testarConexao(
          '127.0.0.2:$_porta',
        );
        expect(okRemoto1, isTrue);

        await _derrubarServidor(processo, _porta);

        // sobe de novo com um certificado DIFERENTE (cert1) na mesma
        // porta -- simula o servidor remoto tendo sido reinstalado
        processo = await _subirServidor(_cert1, _chave1, _porta);

        final okRemoto2 = await apiRemoto.testarConexao(
          '127.0.0.2:$_porta',
        );

        expect(
          okRemoto2,
          isFalse,
          reason:
              'certificado trocado em host nao-local deveria falhar a conexao',
        );
        expect(
          apiRemoto.ultimaFalhaCertificado,
          isNotNull,
          reason: 'deveria ter guardado a falha de certificado pra tela usar',
        );
        expect(apiRemoto.ultimaFalhaCertificado!.host, '127.0.0.2');

        // confirma explicitamente (mesmo fluxo do botão "Confiar" na
        // tela) -- a proxima tentativa volta a funcionar
        await apiRemoto.confiarNoCertificadoQueFalhou();
        expect(apiRemoto.ultimaFalhaCertificado, isNull);

        final okRemoto3 = await apiRemoto.testarConexao(
          '127.0.0.2:$_porta',
        );
        expect(
          okRemoto3,
          isTrue,
          reason: 'depois de confiar de novo, a conexao deveria funcionar',
        );
      } finally {
        if (processo != null) {
          await _derrubarServidor(processo, _porta);
        }
      }
    },
    timeout: const Timeout(Duration(seconds: 60)),
  );

  group('TlsConfianca.ehEnderecoLocal', () {
    test('reconhece os enderecos locais', () {
      expect(TlsConfianca.ehEnderecoLocal('127.0.0.1'), isTrue);
      expect(TlsConfianca.ehEnderecoLocal('localhost'), isTrue);
      expect(TlsConfianca.ehEnderecoLocal('LOCALHOST'), isTrue);
      expect(TlsConfianca.ehEnderecoLocal('  127.0.0.1  '), isTrue);
      expect(TlsConfianca.ehEnderecoLocal('::1'), isTrue);
    });

    test('nao reconhece enderecos de rede como locais', () {
      expect(TlsConfianca.ehEnderecoLocal('192.168.0.10'), isFalse);
      expect(TlsConfianca.ehEnderecoLocal('127.0.0.2'), isFalse);
      expect(TlsConfianca.ehEnderecoLocal('meuservidor.local'), isFalse);
    });
  });

  group('TlsConfianca -- cache em memoria', () {
    test('confiar guarda no cache e persiste', () async {
      _ArmazenamentoFalso().instalar();
      final tls = TlsConfianca();

      expect(tls.certificadoEmMemoria('exemplo.com', 443), isNull);

      await tls.confiar('exemplo.com', 443, '---PEM FALSO---');

      expect(tls.certificadoEmMemoria('exemplo.com', 443), '---PEM FALSO---');
    });

    test('prepararConfianca carrega do storage pro cache', () async {
      _ArmazenamentoFalso().instalar();
      final tls1 = TlsConfianca();
      await tls1.confiar('exemplo.com', 443, '---PEM SALVO---');

      // simula uma nova sessao do app (cache em memoria vazio de
      // novo), mas o storage "persistido" continua com o valor
      final tls2 = TlsConfianca();
      expect(tls2.certificadoEmMemoria('exemplo.com', 443), isNull);

      await tls2.prepararConfianca('exemplo.com', 443);

      expect(tls2.certificadoEmMemoria('exemplo.com', 443), '---PEM SALVO---');
    });
  });
}
