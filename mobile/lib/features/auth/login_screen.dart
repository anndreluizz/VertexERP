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
  void initState() {
    super.initState();
    ref.read(sessaoControllerProvider.notifier).ultimoEmail().then((email) {
      if (mounted && email != null && _emailControlador.text.isEmpty) {
        _emailControlador.text = email;
      }
    });
  }

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
      setState(
        () => _erro = 'Informe um e-mail válido (ex.: nome@exemplo.com).',
      );
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
    final tema = Theme.of(context).textTheme;

    return Scaffold(
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, restricoes) => SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: ConstrainedBox(
              constraints: BoxConstraints(minHeight: restricoes.maxHeight),
              child: IntrinsicHeight(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const SizedBox(height: 28),
                    // mesma marca do Desktop (telas/login.py): "V" no
                    // quadrado azul-marinho + nome
                    Row(
                      children: [
                        Container(
                          width: 40,
                          height: 40,
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            color: VertexColors.primaria,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: const Text(
                            'V',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 18,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Text('Vertex ERP', style: tema.titleMedium),
                      ],
                    ),
                    const Spacer(),
                    const SizedBox(height: 40),
                    Text('Acessar loja', style: tema.headlineMedium),
                    const SizedBox(height: 6),
                    Text(
                      'Entre com suas credenciais para continuar',
                      style: tema.bodyMedium?.copyWith(
                        color: VertexColors.textoSecundario,
                      ),
                    ),
                    const SizedBox(height: 32),
                    Text('E-MAIL', style: tema.labelSmall),
                    const SizedBox(height: 8),
                    TextField(
                      controller: _emailControlador,
                      keyboardType: TextInputType.emailAddress,
                      autofillHints: const [AutofillHints.email],
                      textInputAction: TextInputAction.next,
                      decoration: const InputDecoration(
                        hintText: 'seu@contato.com',
                      ),
                    ),
                    const SizedBox(height: 18),
                    Text('SENHA', style: tema.labelSmall),
                    const SizedBox(height: 8),
                    TextField(
                      controller: _senhaControlador,
                      obscureText: !_senhaVisivel,
                      autofillHints: const [AutofillHints.password],
                      onSubmitted: (_) => _entrar(),
                      decoration: InputDecoration(
                        hintText: '••••••••',
                        suffixIcon: IconButton(
                          tooltip: _senhaVisivel
                              ? 'Ocultar senha'
                              : 'Mostrar senha',
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
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        SizedBox(
                          width: 32,
                          child: Checkbox(
                            value: _lembrar,
                            onChanged: (valor) =>
                                setState(() => _lembrar = valor ?? true),
                          ),
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: GestureDetector(
                            onTap: () => setState(() => _lembrar = !_lembrar),
                            child: Text(
                              'Manter conectado',
                              style: tema.bodyMedium,
                            ),
                          ),
                        ),
                        TextButton(
                          onPressed: _esqueceuSenha,
                          child: const Text('Esqueceu a senha?'),
                        ),
                      ],
                    ),
                    if (_erro != null) ...[
                      const SizedBox(height: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 10,
                        ),
                        decoration: BoxDecoration(
                          color: VertexColors.erroClaro,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Text(
                          _erro!,
                          style: tema.bodyMedium?.copyWith(
                            color: VertexColors.erro,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ],
                    const SizedBox(height: 20),
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
                          : const Text('Entrar'),
                    ),
                    const Spacer(flex: 2),
                    const SizedBox(height: 24),
                    Center(
                      child: TextButton.icon(
                        style: TextButton.styleFrom(
                          foregroundColor: VertexColors.textoSecundario,
                        ),
                        onPressed: _trocarServidor,
                        icon: const Icon(Icons.dns_outlined, size: 18),
                        label: const Text('Configurar servidor'),
                      ),
                    ),
                    const SizedBox(height: 12),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
