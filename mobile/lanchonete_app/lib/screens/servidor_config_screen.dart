import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/sessao_provider.dart';

class ServidorConfigScreen extends StatefulWidget {
  const ServidorConfigScreen({super.key});

  @override
  State<ServidorConfigScreen> createState() => _ServidorConfigScreenState();
}

class _ServidorConfigScreenState extends State<ServidorConfigScreen> {
  final _formKey = GlobalKey<FormState>();
  final _urlController = TextEditingController();
  bool _salvando = false;

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  Future<void> _salvar() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _salvando = true);
    try {
      await context.read<SessaoProvider>().configurarServidor(_urlController.text);
    } finally {
      if (mounted) setState(() => _salvando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Configurar servidor')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Informe o endereço do servidor do VertexERP '
                '(ex.: a URL gerada pelo ngrok, https://xxxx.ngrok-free.app).',
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _urlController,
                keyboardType: TextInputType.url,
                decoration: const InputDecoration(
                  labelText: 'URL do servidor',
                  hintText: 'https://xxxx.ngrok-free.app',
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return 'Informe a URL do servidor';
                  }
                  final uri = Uri.tryParse(value.trim());
                  if (uri == null || !uri.hasScheme) {
                    return 'URL inválida (inclua http:// ou https://)';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 24),
              FilledButton(
                onPressed: _salvando ? null : _salvar,
                child: _salvando
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Salvar e continuar'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
