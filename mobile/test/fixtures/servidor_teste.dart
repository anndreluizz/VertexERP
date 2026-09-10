// Helper compartilhado pelos testes que precisam de um backend HTTPS
// real pra falar com (ver fixtures/servidor_teste.py -- o mesmo
// servidor de teste, portátil, usado tanto pelo teste de paridade TOFU
// quanto pelo teste de 2FA).
import 'dart:io';

/// Executável do Python a usar -- por padrão espera "python" no PATH
/// (é o que `actions/setup-python` deixa configurado no CI). Pra rodar
/// localmente numa máquina onde "python" no PATH não é o interpretador
/// certo (ex.: cai num stub da Microsoft Store no Windows), defina a
/// variável de ambiente PYTHON_EXECUTABLE apontando pro python.exe de
/// verdade antes de rodar `flutter test`.
final String pythonExecutavel =
    Platform.environment['PYTHON_EXECUTABLE'] ?? 'python';

// Caminho relativo ao diretorio de trabalho de onde `flutter test` eh
// chamado -- sempre a raiz do pacote mobile/ (unico jeito suportado de
// rodar flutter test), entao "test/fixtures/..." sempre resolve certo,
// sem depender de Platform.script (que aponta pro harness do flutter
// test, nao pro arquivo de teste, e nao da pra confiar nele aqui).
const String _caminhoServidor = 'test/fixtures/servidor_teste.py';

/// Um processo do servidor de teste (fixtures/servidor_teste.py)
/// rodando numa porta -- start/stop com espera ativa da porta, pra não
/// seguir em frente antes do servidor estar realmente pronto (ou
/// realmente liberado, no caso do stop).
class ServidorTeste {
  ServidorTeste._(this._processo, this.porta);

  final Process _processo;
  final int porta;

  static Future<ServidorTeste> subir(int porta) async {
    final processo = await Process.start(pythonExecutavel, [
      _caminhoServidor,
      porta.toString(),
    ]);

    for (var i = 0; i < 50; i++) {
      try {
        final socket = await Socket.connect(
          '127.0.0.1',
          porta,
          timeout: const Duration(milliseconds: 300),
        );
        await socket.close();
        return ServidorTeste._(processo, porta);
      } catch (_) {
        await Future.delayed(const Duration(milliseconds: 200));
      }
    }

    processo.kill();
    throw StateError(
      'servidor de teste não subiu a tempo -- confira se "$pythonExecutavel" '
      'existe e tem fastapi/uvicorn/cryptography instalados '
      '(ver test/fixtures/requirements.txt)',
    );
  }

  Future<void> derrubar() async {
    _processo.kill();
    await _processo.exitCode;

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
}
