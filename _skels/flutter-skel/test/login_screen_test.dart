/// LoginScreen — widget tests.
///
/// Verifies form rendering, submission via [ItemsClient.loginWithPassword],
/// token-store integration, and error display. Uses a [MockClient] so
/// no real backend is needed.

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_skel/api/items_client.dart';
import 'package:flutter_skel/auth/auth_scope.dart';
import 'package:flutter_skel/auth/token_store.dart';
import 'package:flutter_skel/config.dart';
import 'package:flutter_skel/screens/login_screen.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const _config = AppConfig(
  backendUrl: 'http://test-host:8000',
  jwt: JwtConfig(
    algorithm: 'HS256',
    issuer: 'devskel',
    accessTtl: 3600,
    refreshTtl: 604800,
  ),
  services: <String, String>{},
);

Widget _wrap(Widget child, TokenStore store) {
  return AuthScope(
    store: store,
    child: MaterialApp(home: Scaffold(body: child)),
  );
}

void main() {
  late TokenStore tokenStore;

  setUp(() {
    tokenStore = TokenStore.instance;
    tokenStore.value = null;
  });

  tearDown(() {
    tokenStore.value = null;
  });

  testWidgets('renders username + password fields and a sign-in button',
      (WidgetTester tester) async {
    final client = ItemsClient(
      config: _config,
      tokenStore: tokenStore,
      client: MockClient((_) async => http.Response('', 500)),
    );
    await tester.pumpWidget(_wrap(LoginScreen(client: client), tokenStore));

    expect(find.text('Sign in'), findsWidgets);
    expect(find.byType(TextField), findsNWidgets(2));
    expect(find.byType(FilledButton), findsOneWidget);
  });

  testWidgets('sets token on successful login', (WidgetTester tester) async {
    final client = ItemsClient(
      config: _config,
      tokenStore: tokenStore,
      client: MockClient((http.Request request) async {
        if (request.url.path == '/api/auth/login') {
          return http.Response(
            jsonEncode(const <String, String>{'access': 'test-jwt-token'}),
            200,
            headers: const <String, String>{'content-type': 'application/json'},
          );
        }
        return http.Response('', 404);
      }),
    );

    await tester.pumpWidget(_wrap(LoginScreen(client: client), tokenStore));

    await tester.enterText(find.byType(TextField).first, 'alice');
    await tester.enterText(find.byType(TextField).last, 'pass');
    await tester.tap(find.byType(FilledButton));
    await tester.pumpAndSettle();

    expect(tokenStore.value, equals('test-jwt-token'));
    expect(tokenStore.isAuthenticated, isTrue);
  });

  testWidgets('displays error on invalid credentials',
      (WidgetTester tester) async {
    final client = ItemsClient(
      config: _config,
      tokenStore: tokenStore,
      client: MockClient((http.Request request) async {
        if (request.url.path == '/api/auth/login') {
          return http.Response('Unauthorized', 401);
        }
        return http.Response('', 404);
      }),
    );

    await tester.pumpWidget(_wrap(LoginScreen(client: client), tokenStore));

    await tester.enterText(find.byType(TextField).first, 'alice');
    await tester.enterText(find.byType(TextField).last, 'wrong');
    await tester.tap(find.byType(FilledButton));
    await tester.pumpAndSettle();

    expect(find.textContaining('Invalid'), findsOneWidget);
    expect(tokenStore.value, isNull);
  });
}
