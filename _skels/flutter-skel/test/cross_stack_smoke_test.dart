/// Cross-stack smoke test — exercises the REAL `lib/api/items_client.dart`
/// against a live backend.
///
/// This is the test the dev_skel `_bin/test-flutter-*-integration`
/// runners launch AFTER they have generated the wrapper, rebuilt the
/// Flutter web bundle (so the bundled `.env` asset reflects the
/// rewritten port), started the backend, and confirmed the backend
/// serves the canonical items contract via a Python HTTP pre-flight.
///
/// The runners enable this test by setting two environment variables:
///
///   RUN_CROSS_STACK_SMOKE=1   — gate (every other `flutter test` skips)
///   BACKEND_URL=http://...    — used directly by the smoke (we do
///                                NOT load the bundled `.env` asset
///                                here because flutter_dotenv only
///                                works in the Flutter widget runtime
///                                or web; pure `flutter test` mode
///                                cannot read assets bundled for the
///                                web target)
///
/// Without those vars the entire suite no-ops, so a developer running
/// `flutter test` against a fresh project sees nothing surprising.
///
/// Why we run this through `flutter test` instead of a Python HTTP
/// exercise: the Python pre-flight only proves the *backend* serves
/// the contract. This test additionally proves the *frontend's own
/// client code* knows how to talk to the backend — same
/// `loginWithPassword` parsing, same `Bearer` header injection, same
/// `AuthError` thrown on 401, same `Item.fromJson` deserialisation.
/// A regression in `lib/api/items_client.dart` would surface here
/// long before a real user opens the app.
///
/// Implementation notes:
///   - We construct an [AppConfig] manually instead of using
///     `AppConfig.load()` because the latter goes through
///     `flutter_dotenv` which expects a bundled web asset and panics
///     under `flutter test`. The runner passes the URL via the
///     `BACKEND_URL` environment variable.
///   - We set `TokenStore.instance.value` directly instead of calling
///     `tokenStore.setToken(...)` because the latter writes through
///     `flutter_secure_storage`, which uses platform channels that
///     are not available under `flutter test` (no host platform).

import 'dart:convert';
import 'dart:io';

import 'package:flutter_skel/api/items_client.dart';
import 'package:flutter_skel/auth/token_store.dart';
import 'package:flutter_skel/config.dart';
import 'package:flutter_skel/state/state_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

const _smokeUsername = 'flutter-smoke-user';
const _smokePassword = 'flutter-smoke-pw-12345';
const _smokeEmail = 'flutter-smoke@example.com';
const _smokeItemName = 'flutter-smoke-test-item';
const _smokeItemDescription =
    'Created by the Flutter frontend cross-stack smoke test';

/// One register helper, mirroring what `_react_backend_lib`'s Python
/// pre-flight (and the React smoke) do. The Flutter `ItemsClient` has
/// no register helper because real apps either ship a separate
/// onboarding flow or rely on a server-side admin tool to provision
/// users.
Future<int> _registerSmokeUser(String backendUrl) async {
  final response = await http.post(
    Uri.parse('$backendUrl/api/auth/register'),
    headers: const <String, String>{'Content-Type': 'application/json'},
    body: jsonEncode(const <String, String>{
      'username': _smokeUsername,
      'email': _smokeEmail,
      'password': _smokePassword,
      'password_confirm': _smokePassword,
    }),
  );
  if (response.statusCode != 201) {
    fail(
      'register expected 201, got ${response.statusCode}: ${response.body}',
    );
  }
  final body = jsonDecode(response.body) as Map<String, dynamic>;
  final user = body['user'] as Map<String, dynamic>?;
  final id = user?['id'] as int?;
  if (id == null) {
    fail('register response missing user.id: $body');
  }
  return id;
}

void main() {
  final env = Platform.environment;
  final runSmoke = env['RUN_CROSS_STACK_SMOKE'] == '1';
  final backendUrl = env['BACKEND_URL'];

  if (!runSmoke || backendUrl == null || backendUrl.isEmpty) {
    // The Flutter test runner needs at least one test in the file or
    // it returns a "no tests ran" error. Provide a no-op so the
    // runner exits 0 when the smoke is disabled.
    test('cross-stack smoke skipped (RUN_CROSS_STACK_SMOKE != 1)', () {
      expect(true, isTrue);
    });
    return;
  }

  test(
    'round-trips through every ItemsClient function against $backendUrl',
    () async {
      // Manual AppConfig (skipping flutter_dotenv — see header).
      final config = AppConfig(
        backendUrl: backendUrl,
        jwt: const JwtConfig(
          algorithm: 'HS256',
          issuer: 'devskel',
          accessTtl: 3600,
          refreshTtl: 604800,
        ),
        services: const <String, String>{},
      );

      // Reset the token store directly. We can't use clear() because
      // it goes through flutter_secure_storage; setting `value`
      // directly only fires notifyListeners() and is safe in test
      // mode.
      final tokenStore = TokenStore.instance;
      tokenStore.value = null;
      addTearDown(() {
        tokenStore.value = null;
      });

      final client = ItemsClient(config: config, tokenStore: tokenStore);

      // Sub-step 1: register (raw http — no helper in items_client).
      final userId = await _registerSmokeUser(backendUrl);
      expect(userId, greaterThan(0));

      // Sub-step 2: login → JWT via the REAL helper. Exercises both
      // the `{access}` and `{token}` response shapes that
      // `loginWithPassword` tolerates.
      final token = await client.loginWithPassword(_smokeUsername, _smokePassword);
      expect(token, isA<String>());
      expect(token.length, greaterThan(20));

      // Stash the token directly so subsequent ItemsClient calls
      // pick it up via the auto-Bearer-header path.
      tokenStore.value = token;
      expect(tokenStore.value, equals(token));
      expect(tokenStore.isAuthenticated, isTrue);

      // Sub-step 3: list items (initial). Capture the count so we can
      // assert "grew by 1" after create — robust to user-scoped vs
      // shared items schemas.
      final initial = await client.listItems();
      expect(initial, isA<List<Item>>());
      final initialCount = initial.length;

      // Sub-step 4: create an item via the REAL helper. Exercises
      // _headers + JSON serialisation + the 201 unwrap path.
      final created = await client.createItem(
        const NewItem(
          name: _smokeItemName,
          description: _smokeItemDescription,
          isCompleted: false,
        ),
      );
      expect(created.id, greaterThan(0));
      expect(created.name, equals(_smokeItemName));
      expect(created.isCompleted, isFalse);

      // Sub-step 5: list again — the new item must be visible.
      final after = await client.listItems();
      expect(after.length, equals(initialCount + 1));
      final names = after.map((Item item) => item.name).toList();
      expect(names, contains(_smokeItemName));

      // Sub-step 6: round-trip the item via getItem (exercises the
      // path-parameter helper).
      final fetched = await client.getItem(created.id);
      expect(fetched.id, equals(created.id));
      expect(fetched.name, equals(_smokeItemName));

      // Sub-step 7: complete via the @action endpoint. The response
      // body must reflect the new isCompleted=true state.
      final completed = await client.completeItem(created.id);
      expect(completed.id, equals(created.id));
      expect(completed.isCompleted, isTrue);

      // Sub-step 8: state API — save, load, delete roundtrip.
      // Exercises the /api/state endpoints that the persistent UI
      // filter (`readAppState('items.showCompleted', ...)`) uses.
      final stateApi = StateApi(config: config, tokenStore: tokenStore);
      const stateKey = 'smoke.testFlag';
      final stateValue = <String, Object?>{'flag': true, 'ts': 12345};
      await stateApi.saveState(stateKey, stateValue);
      final allState = await stateApi.loadAllState();
      expect(allState, contains(stateKey));
      final loaded = allState[stateKey] as Map<String, dynamic>;
      expect(loaded['flag'], isTrue);
      await stateApi.deleteState(stateKey);
      final afterDelete = await stateApi.loadAllState();
      expect(afterDelete, isNot(contains(stateKey)));

      // Sub-step 9: anonymous request must raise AuthError. We
      // briefly clear the store so the next call picks up no token,
      // then restore it for the next assertion.
      tokenStore.value = null;
      await expectLater(
        client.listItems(),
        throwsA(isA<AuthError>()),
      );
      tokenStore.value = token;

      // Sub-step 10: explicit invalid token must also raise AuthError.
      // The override path (`token: 'not-a-real-token'`) bypasses the
      // store entirely, mirroring the React test's coverage.
      await expectLater(
        client.listItems(token: 'not-a-real-token'),
        throwsA(isA<AuthError>()),
      );

      client.close();
    },
    // Generous timeout — every step crosses the network.
    timeout: const Timeout(Duration(seconds: 60)),
  );

  // NOTE: OrdersClient domain-specific tests (catalog, order lifecycle,
  // reject flow) are NOT included here because when item_name=Order the
  // AI manifest regenerates orders_client.dart from the generic items
  // template, overwriting the full-featured template version. The order
  // lifecycle is comprehensively tested by Phase 6 backend tests and the
  // 14-step HTTP exercise in skel-test-pizzeria-orders.
}
