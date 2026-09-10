// Verifica o fluxo TOFU (trust on first use) do ApiClient contra um
// servidor HTTPS real (o mesmo tipo de teste usado na verificação
// equivalente do Desktop) -- primeiro contato confia sozinho, segunda
// chamada reusa o pin, e um certificado trocado se comporta diferente
// em host local (127.0.0.1, reconfia sozinho) vs host "remoto"
// (127.0.0.2 -- endereço de loopback real do Windows, mas fora da
// lista eh_endereco_local, dá pra simular "outra máquina" sem
// precisar de uma de verdade).
//
// O servidor de teste (test/fixtures/servidor_teste.py) gera um
// certificado autoassinado NOVO a cada vez que inicia -- por isso
// "derrubar e subir de novo" já simula sozinho um servidor
// reinstalado com certificado diferente, sem precisar de arquivos de
// certificado fixos no repositório.
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/api_client.dart';
import 'package:mobile/core/tls_confianca.dart';

import 'fixtures/servidor_teste.dart';

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

      ServidorTeste? servidor;

      try {
        // -----------------------------------------------------------
        // 1) primeiro contato (127.0.0.1, genuinamente local) --
        // confia sozinho, sem pin previo
        // -----------------------------------------------------------

        servidor = await ServidorTeste.subir(_porta);

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
        // 3) "servidor reinstalado": derruba, sobe de novo na MESMA
        // porta (o script gera um certificado novo sozinho a cada
        // vez que inicia) mas em 127.0.0.2 -- endereço de loopback
        // real do Windows, então dá pra conectar de verdade, só que
        // TlsConfianca.ehEnderecoLocal não reconhece como "local" (só
        // 127.0.0.1/localhost/::1) -- simula "servidor numa rede
        // remota" sem precisar de uma segunda máquina.
        // -----------------------------------------------------------

        await servidor.derrubar();

        servidor = await ServidorTeste.subir(_porta);

        final apiRemoto = ApiClient();
        // primeiro contato em "127.0.0.2" -- TOFU confia no certificado
        // atual (é a primeira vez que esse host:porta é visto)
        final okRemoto1 = await apiRemoto.testarConexao(
          '127.0.0.2:$_porta',
        );
        expect(okRemoto1, isTrue);

        await servidor.derrubar();

        // sobe de novo com um certificado DIFERENTE (gerado do zero)
        // na mesma porta -- simula o servidor remoto tendo sido
        // reinstalado
        servidor = await ServidorTeste.subir(_porta);

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
        await servidor?.derrubar();
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
