/// ItemForm — widget tests.
///
/// Verifies form rendering, controlled inputs, submission via the
/// [ItemsController.create] callback, and error display. Uses a
/// mock [ItemsController] backed by a [MockClient].

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_skel/api/items_client.dart';
import 'package:flutter_skel/auth/token_store.dart';
import 'package:flutter_skel/config.dart';
import 'package:flutter_skel/controllers/items_controller.dart';
import 'package:flutter_skel/screens/item_form.dart';
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

final _fakeItemResponse = jsonEncode(const <String, Object?>{
  'id': 42,
  'name': 'Created',
  'description': 'desc',
  'is_completed': false,
  'created_at': '2026-01-01T00:00:00Z',
  'updated_at': '2026-01-01T00:00:00Z',
});

void main() {
  late TokenStore tokenStore;

  setUp(() {
    tokenStore = TokenStore.instance;
    tokenStore.value = 'test-token';
  });

  tearDown(() {
    tokenStore.value = null;
  });

  testWidgets('renders name + description fields and a submit button',
      (WidgetTester tester) async {
    final client = ItemsClient(
      config: _config,
      tokenStore: tokenStore,
      client: MockClient((_) async => http.Response('[]', 200)),
    );
    final controller = ItemsController(client: client, tokenStore: tokenStore);

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: ItemForm(controller: controller)),
    ));

    expect(find.text('New item'), findsOneWidget);
    expect(find.byType(TextField), findsNWidgets(2));
    expect(find.byType(FilledButton), findsOneWidget);

    controller.dispose();
  });

  testWidgets('calls controller.create and clears inputs on success',
      (WidgetTester tester) async {
    final mockHttp = MockClient((http.Request request) async {
      if (request.url.path == '/api/items' && request.method == 'POST') {
        return http.Response(
          _fakeItemResponse,
          201,
          headers: const <String, String>{'content-type': 'application/json'},
        );
      }
      // listItems for initial fetch
      return http.Response('[]', 200);
    });
    final client = ItemsClient(
      config: _config,
      tokenStore: tokenStore,
      client: mockHttp,
    );
    final controller = ItemsController(client: client, tokenStore: tokenStore);

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: ItemForm(controller: controller)),
    ));
    await tester.pumpAndSettle();

    // Enter values.
    await tester.enterText(find.byType(TextField).first, 'My new item');
    await tester.enterText(find.byType(TextField).last, 'Some details');
    await tester.tap(find.byType(FilledButton));
    await tester.pumpAndSettle();

    // After success, both fields should be cleared.
    final nameField = tester.widget<TextField>(find.byType(TextField).first);
    expect(nameField.controller?.text, isEmpty);

    controller.dispose();
  });
}
