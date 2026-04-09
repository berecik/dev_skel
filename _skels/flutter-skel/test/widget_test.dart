/// Smoke test for the dev_skel Flutter skeleton.
///
/// Pumps the root widget tree with a fake [ItemsClient] (so the test
/// runner does not try to hit a real backend) and asserts that the
/// LoginScreen renders when the token store is empty.
///
/// We deliberately keep this minimal — the goal is to give
/// `flutter test` something to run during `test_skel` so the
/// generator E2E pipeline catches obvious compile errors. Higher-level
/// integration tests (real backend, real HTTP) are tracked as a
/// follow-up.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:flutter_skel/api/items_client.dart';
import 'package:flutter_skel/auth/auth_scope.dart';
import 'package:flutter_skel/auth/token_store.dart';
import 'package:flutter_skel/config.dart';
import 'package:flutter_skel/screens/login_screen.dart';

void main() {
  testWidgets('renders the login screen when no token is stored',
      (WidgetTester tester) async {
    // Build a never-hit fake HTTP client. The login screen does not
    // call the backend until the user taps "Sign in", so any request
    // hitting this stub is a real bug.
    final fakeHttp = MockClient((http.Request request) async {
      throw StateError('LoginScreen made an unexpected request to ${request.url}');
    });

    const config = AppConfig(
      backendUrl: 'http://localhost:8000',
      jwt: JwtConfig(
        algorithm: 'HS256',
        issuer: 'devskel',
        accessTtl: 3600,
        refreshTtl: 604800,
      ),
      services: <String, String>{},
    );

    final tokenStore = TokenStore.instance;
    // Reset to a known state so prior tests do not bleed in.
    tokenStore.value = null;

    final itemsClient = ItemsClient(
      config: config,
      tokenStore: tokenStore,
      client: fakeHttp,
    );

    await tester.pumpWidget(
      AuthScope(
        store: tokenStore,
        child: MaterialApp(
          home: Scaffold(
            body: LoginScreen(client: itemsClient),
          ),
        ),
      ),
    );

    expect(find.text('Sign in'), findsWidgets);
    expect(find.byType(TextField), findsNWidgets(2));
  });
}
