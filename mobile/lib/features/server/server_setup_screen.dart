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

    _mostrar(
      ok
          ? 'Conectado com sucesso!'
          : 'Não foi possível conectar agora — confira se o servidor está ligado e na mesma rede.',
      ok ? VertexColors.secundaria : VertexColors.alerta,
    );
  }

  Future<void> _salvar() async {
    final endereco = _controlador.text.trim();
    if (endereco.isEmpty) {
      _mostrar('Informe o endereço do servidor.', VertexColors.alerta);
      return;
    }

    setState(() => _salvando = true);
    await ref.read(sessaoControllerProvider.notifier).configurarServidor(
      endereco,
    );
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
                Container(
                  width: 64,
                  height: 64,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: VertexColors.primariaClara,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Icon(
                    Icons.storefront_outlined,
                    color: VertexColors.primaria,
                    size: 30,
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
