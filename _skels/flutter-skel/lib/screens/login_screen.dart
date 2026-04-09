/// `LoginScreen` — minimal username/password form that hits the
/// wrapper-shared `/api/auth/login` endpoint and stores the resulting
/// JWT in the shared [TokenStore].
///
/// Mirrors React's `LoginForm.tsx`. Uses controlled
/// [TextEditingController]s and a `setState`-driven `submitting` flag.

import 'package:flutter/material.dart';

import '../api/items_client.dart';
import '../auth/auth_scope.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.client});

  final ItemsClient client;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final TextEditingController _username = TextEditingController();
  final TextEditingController _password = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _username.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_username.text.isEmpty || _password.text.isEmpty) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final token = await widget.client.loginWithPassword(
        _username.text,
        _password.text,
      );
      await AuthScope.read(context).setToken(token);
    } on AuthError {
      setState(() => _error = 'Invalid username or password.');
    } catch (err) {
      setState(() => _error = err.toString());
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 360),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Text(
                'Sign in',
                style: Theme.of(context).textTheme.headlineSmall,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _username,
                autofillHints: const <String>[AutofillHints.username],
                decoration: const InputDecoration(labelText: 'Username'),
                textInputAction: TextInputAction.next,
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _password,
                autofillHints: const <String>[AutofillHints.password],
                obscureText: true,
                decoration: const InputDecoration(labelText: 'Password'),
                onSubmitted: (_) => _submit(),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: _submitting ? null : _submit,
                child: Text(_submitting ? 'Signing in…' : 'Sign in'),
              ),
              if (_error != null) ...<Widget>[
                const SizedBox(height: 12),
                Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                  textAlign: TextAlign.center,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
