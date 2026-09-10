import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../theme/vertex_colors.dart';

/// Checagem de formato simples (não verifica se o domínio existe de
/// verdade) -- só o suficiente pra pegar erro de digitação óbvio antes
/// de gastar uma ida à rede, mesmo critério usado no Desktop
/// (frontend/utils/validacao.py::email_valido).
final _regexEmail = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _emailControlador = TextEditingController();
  final _senhaControlador = TextEditingController();

  bool _senhaVisivel = false;
  bool _lembrar = true;
  bool _entrando = false;
  String? _erro;

  @override
  void dispose() {
    _emailControlador.dispose();
    _senhaControlador.dispose();
    super.dispose();
  }

  Future<void> _entrar() async {
    final email = _emailControlador.text.trim();
    final senha = _senhaControlador.text;

    if (email.isEmpty || senha.isEmpty) {
      setState(() => _erro = 'Informe o e-mail e a senha.');
      return;
    }

    if (!_regexEmail.hasMatch(email)) {
      setState(() => _erro = 'Informe um e-mail válido (ex.: nome@exemplo.com).');
      return;
    }

    setState(() {
      _entrando = true;
      _erro = null;
    });

    final resultado = await ref
        .read(sessaoControllerProvider.notifier)
        .login(email, senha, lembrar: _lembrar);

    if (!mounted) return;

    if (resultado.verificacaoId != null) {
      // senha certa, falta o segundo fator (2FA) -- o codigo ja foi
      // mandado por e-mail nesse momento (ver SessaoController.login)
      setState(() => _entrando = false);

      final codigo = await _pedirCodigo2fa(email);

      if (codigo == null || codigo.isEmpty || !mounted) return;

      setState(() => _entrando = true);

      final erroVerificacao = await ref
          .read(sessaoControllerProvider.notifier)
          .verificarCodigo2fa(
            resultado.verificacaoId!,
            codigo,
            lembrar: _lembrar,
          );

      if (!mounted) return;

      setState(() {
        _entrando = false;
        _erro = erroVerificacao;
      });

      return;
    }

    setState(() {
      _entrando = false;
      _erro = resultado.erro;
    });
  }

  /// Pede o codigo de 6 digitos mandado por e-mail -- devolve o texto
  /// digitado, ou null se o usuario cancelou.
  Future<String?> _pedirCodigo2fa(String email) {
    final controlador = TextEditingController();

    return showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Verificação em duas etapas'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Mandamos um código de 6 dígitos para $email.'),
            const SizedBox(height: 12),
            TextField(
              controller: controlador,
              keyboardType: TextInputType.number,
              maxLength: 6,
              autofocus: true,
              decoration: const InputDecoration(labelText: 'Código'),
              onSubmitted: (valor) =>
                  Navigator.of(dialogContext).pop(valor.trim()),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(null),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () =>
                Navigator.of(dialogContext).pop(controlador.text.trim()),
            child: const Text('Confirmar'),
          ),
        ],
      ),
    );
  }

  void _esqueceuSenha() {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Esqueceu a senha?'),
        content: const Text(
          'Entre em contato com o administrador da loja pra redefinir '
          'sua senha.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Entendi'),
          ),
        ],
      ),
    );
  }

  void _trocarServidor() {
    ref.read(sessaoControllerProvider.notifier).trocarServidor();
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
                const SizedBox(height: 12),
                Text(
                  'VERTEX ERP',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const SizedBox(height: 2),
                Text(
                  'GESTÃO NA PALMA DA MÃO',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: VertexColors.textoTerciario,
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1,
                  ),
                ),
                const SizedBox(height: 34),
                TextField(
                  controller: _emailControlador,
                  keyboardType: TextInputType.emailAddress,
                  decoration: const InputDecoration(
                    labelText: 'E-mail',
                    hintText: 'seu@contato.com',
                  ),
                ),
                const SizedBox(height: 14),
                TextField(
                  controller: _senhaControlador,
                  obscureText: !_senhaVisivel,
                  onSubmitted: (_) => _entrar(),
                  decoration: InputDecoration(
                    labelText: 'Senha',
                    suffixIcon: IconButton(
                      icon: Icon(
                        _senhaVisivel
                            ? Icons.visibility_off_outlined
                            : Icons.visibility_outlined,
                      ),
                      onPressed: () =>
                          setState(() => _senhaVisivel = !_senhaVisivel),
                    ),
                  ),
                ),
                const SizedBox(height: 6),
                Row(
                  children: [
                    Checkbox(
                      value: _lembrar,
                      onChanged: (valor) =>
                          setState(() => _lembrar = valor ?? true),
                    ),
                    const Expanded(child: Text('Manter conectado')),
                  ],
                ),
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    style: TextButton.styleFrom(
                      padding: EdgeInsets.zero,
                      minimumSize: Size.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                    onPressed: _esqueceuSenha,
                    child: const Text('Esqueceu a senha?'),
                  ),
                ),
                if (_erro != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    _erro!,
                    style: const TextStyle(
                      color: VertexColors.erro,
                      fontSize: 13.5,
                    ),
                  ),
                ],
                const SizedBox(height: 18),
                ElevatedButton(
                  onPressed: _entrando ? null : _entrar,
                  child: _entrando
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Text('ACESSAR SISTEMA'),
                ),
                const SizedBox(height: 18),
                Center(
                  child: TextButton(
                    onPressed: _trocarServidor,
                    child: const Text('Configurar servidor'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
