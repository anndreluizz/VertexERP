import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Confia no certificado autoassinado do servidor via TOFU (trust on
/// first use -- mesmo modelo do SSH com known_hosts): sem CA de
/// verdade (servidor local, só IP na rede da loja, sem domínio), o
/// app aprende a confiar no certificado do Servidor na primeira
/// conexão bem sucedida, e passa a EXIGIR esse mesmo certificado dali
/// pra frente -- se um dia vier diferente, é sinal de servidor
/// reinstalado (esperado depois de trocar de máquina) ou de algo
/// suspeito na rede.
class TlsConfianca {
  TlsConfianca() : _storage = const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  // dart:io's HttpClient.badCertificateCallback é SÍNCRONO -- sem
  // jeito de ler o secure storage (que é async) direto dele. Por isso
  // esse cache em memória, pré-carregado (ver prepararConfianca) antes
  // de qualquer requisição de verdade acontecer.
  final Map<String, String> _cache = {};

  static String _chave(String host, int porta) =>
      'certificado_confiavel_${host}_$porta';

  static String _chaveMapa(String host, int porta) => '$host:$porta';

  static bool ehEnderecoLocal(String host) {
    final normalizado = host.trim().toLowerCase();
    return normalizado == '127.0.0.1' ||
        normalizado == 'localhost' ||
        normalizado == '::1';
  }

  /// Chamado antes de qualquer requisição pra esse host:porta -- traz
  /// o certificado já confiado numa sessão anterior do app (se
  /// algum foi salvo) pro cache em memória, que o
  /// badCertificateCallback (síncrono) consegue ler na hora.
  Future<void> prepararConfianca(String host, int porta) async {
    final chaveMapa = _chaveMapa(host, porta);

    if (_cache.containsKey(chaveMapa)) return;

    final salvo = await _storage.read(key: _chave(host, porta));

    if (salvo != null) {
      _cache[chaveMapa] = salvo;
    }
  }

  String? certificadoEmMemoria(String host, int porta) =>
      _cache[_chaveMapa(host, porta)];

  Future<void> confiar(String host, int porta, String pem) async {
    _cache[_chaveMapa(host, porta)] = pem;
    await _storage.write(key: _chave(host, porta), value: pem);
  }
}
