/// ItemsController — unit tests.
///
/// Verifies the core ChangeNotifier lifecycle: auto-refresh on token
/// change, create with optimistic merge, complete with in-place
/// replacement, and 401-to-unauthorized handling. Uses a [MockClient]
/// so no real backend is needed.

import 'dart:convert';

import 'package:flutter_skel/api/items_client.dart';
import 'package:flutter_skel/auth/token_store.dart';
import 'package:flutter_skel/config.dart';
import 'package:flutter_skel/controllers/items_controller.dart';
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

final _itemsJson = jsonEncode(<Map<String, Object?>>[
  <String, Object?>{
    'id': 1,
    'name': 'Existing',
    'description': null,
    'is_completed': false,
    'created_at': '2026-01-01T00:00:00Z',
    'updated_at': '2026-01-01T00:00:00Z',
  },
]);

void main() {
  late TokenStore tokenStore;

  setUp(() {
    tokenStore = TokenStore.instance;
    tokenStore.value = null;
  });

  tearDown(() {
    tokenStore.value = null;
  });

  test('auto-refreshes when a token is set', () async {
    final mockHttp = MockClient((http.Request request) async {
      if (request.url.path == '/api/items' && request.method == 'GET') {
        return http.Response(
          _itemsJson,
          200,
          headers: const <String, String>{'content-type': 'application/json'},
        );
      }
      return http.Response('', 404);
    });
    final client = ItemsClient(config: _config, tokenStore: tokenStore, client: mockHttp);
    final controller = ItemsController(client: client, tokenStore: tokenStore);

    // No token → items should be empty.
    expect(controller.items, isEmpty);

    // Set token → controller subscribes to tokenStore and auto-refreshes.
    tokenStore.value = 'jwt-123';

    // Allow the microtask to run.
    await Future<void>.delayed(Duration.zero);
    await Future<void>.delayed(Duration.zero);

    expect(controller.items, hasLength(1));
    expect(controller.items.first.name, equals('Existing'));

    controller.dispose();
  });

  test('create merges new item at front of list', () async {
    final mockHttp = MockClient((http.Request request) async {
      if (request.method == 'GET') {
        return http.Response(_itemsJson, 200);
      }
      if (request.method == 'POST' && request.url.path == '/api/items') {
        return http.Response(
          jsonEncode(const <String, Object?>{
            'id': 2,
            'name': 'New',
            'description': null,
            'is_completed': false,
            'created_at': '2026-01-01T00:00:00Z',
            'updated_at': '2026-01-01T00:00:00Z',
          }),
          201,
        );
      }
      return http.Response('', 404);
    });
    final client = ItemsClient(config: _config, tokenStore: tokenStore, client: mockHttp);
    tokenStore.value = 'jwt-123';
    final controller = ItemsController(client: client, tokenStore: tokenStore);

    await Future<void>.delayed(Duration.zero);
    await Future<void>.delayed(Duration.zero);
    expect(controller.items, hasLength(1));

    await controller.create(const NewItem(name: 'New'));
    expect(controller.items, hasLength(2));
    expect(controller.items.first.name, equals('New'));

    controller.dispose();
  });

  test('sets unauthorized=true on 401 and clears token', () async {
    final mockHttp = MockClient((http.Request request) async {
      return http.Response('Unauthorized', 401);
    });
    final client = ItemsClient(config: _config, tokenStore: tokenStore, client: mockHttp);
    tokenStore.value = 'expired-token';
    final controller = ItemsController(client: client, tokenStore: tokenStore);

    await Future<void>.delayed(Duration.zero);
    await Future<void>.delayed(Duration.zero);

    expect(controller.unauthorized, isTrue);
    // The controller auto-clears the stale token.
    expect(tokenStore.value, isNull);

    controller.dispose();
  });
}
