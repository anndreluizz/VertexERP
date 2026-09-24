import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../theme/vertex_colors.dart';

class ServerSetupScreen extends ConsumerStatefulWidget {
  const ServerSetupScreen({super.key});

  @override
  ConsumerState<ServerSetupScreen> createState() => _ServerSetupScreenState();
}

class _ServerSetupScreenState extends ConsumerState<ServerSetupScreen> {
  final _controlador = TextEditingController();
  bool _testando = false;
  bool _salvando = false;
  String? _mensagem;
  Color? _corMensagem;

  @override
  void dispose() {
    _controlador.dispose();
    super.dispose();
  }

  Future<void> _testar() async {
    final endereco = _controlador.text.trim();
    if (endereco.isEmpty) {
      _mostrar('Informe o endereço do servidor.', VertexColors.alerta);
      return;
    }

    setState(() => _testando = true);

    final ok = await ref
        .read(sessaoControllerProvider.notifier)
        .configurarServidor(endereco);

    if (!mounted) return;
    setState(() => _testando = false);

    if (!ok) {
      final falha = ref.read(apiClientProvider).ultimaFalhaCertificado;

      if (falha != null) {
        await _perguntarConfiarDeNovo();
        return;
      }
    }

    _mostrar(
      ok
          ? 'Conectado com sucesso!'
          : 'Não foi possível conectar agora — confira se o servidor está ligado e na mesma rede.',
      ok ? VertexColors.secundaria : VertexColors.alerta,
    );
  }

  /// O certificado salvo pra esse servidor não bate mais com o que
  /// ele está apresentando agora -- normal depois de reinstalar o
  /// Servidor (ver core/tls_confianca.dart), mas também o sinal de
  /// segurança que justifica não confiar automaticamente sem
  /// perguntar, diferente do primeiro contato.
  Future<void> _perguntarConfiarDeNovo() async {
    final confirmar = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Certificado do servidor mudou'),
        content: const Text(
          'O certificado deste servidor é diferente do que estava '
          'salvo como confiável.\n\n'
          'Isso é esperado se o Servidor foi reinstalado ou trocou de '
          'computador recentemente. Se você não fez nenhuma mudança '
          'assim, pode ser um problema de segurança na rede.\n\n'
          'Confiar no certificado atual mesmo assim?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Não'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Confiar'),
          ),
        ],
      ),
    );

    if (confirmar != true || !mounted) {
      _mostrar(
        'Conexão não confirmada — o certificado salvo anteriormente '
        'continua sendo exigido.',
        VertexColors.alerta,
      );
      return;
    }

    await ref.read(apiClientProvider).confiarNoCertificadoQueFalhou();
    await _testar();
  }

  Future<void> _salvar() async {
    final endereco = _controlador.text.trim();
    if (endereco.isEmpty) {
      _mostrar('Informe o endereço do servidor.', VertexColors.alerta);
      return;
    }

    setState(() => _salvando = true);
    await ref
        .read(sessaoControllerProvider.notifier)
        .configurarServidor(endereco);
    if (!mounted) return;
    setState(() => _salvando = false);
  }

  void _mostrar(String texto, Color cor) {
    setState(() {
      _mensagem = texto;
      _corMensagem = cor;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 28),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // marca do Vertex (mesma do login/Desktop); Center porque
                // a coluna estica os filhos pra largura toda
                Center(
                  child: Container(
                    width: 52,
                    height: 52,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: VertexColors.primaria,
                      borderRadius: BorderRadius.circular(15),
                    ),
                    child: const Text(
                      'V',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 23,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                Text(
                  'Conectar à loja',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  'Informe o endereço do computador que funciona como '
                  'servidor do Vertex ERP da sua loja.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: VertexColors.textoSecundario),
                ),
                const SizedBox(height: 28),
                TextField(
                  controller: _controlador,
                  keyboardType: TextInputType.url,
                  decoration: const InputDecoration(
                    labelText: 'Endereço do servidor',
                    hintText: 'Ex.: 192.168.0.10',
                  ),
                ),
                if (_mensagem != null) ...[
                  const SizedBox(height: 14),
                  Text(
                    _mensagem!,
                    textAlign: TextAlign.center,
                    style: TextStyle(color: _corMensagem, fontSize: 13.5),
                  ),
                ],
                const SizedBox(height: 22),
                OutlinedButton(
                  onPressed: _testando ? null : _testar,
                  style: OutlinedButton.styleFrom(
                    minimumSize: const Size.fromHeight(52),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: _testando
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Testar conexão'),
                ),
                const SizedBox(height: 10),
                ElevatedButton(
                  onPressed: _salvando ? null : _salvar,
                  child: _salvando
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Text('Salvar e continuar'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
