/// Wrapper-shared JWT bearer token store.
///
/// Mirrors React's `src/auth/token-store.ts` — the value is persisted
/// to native secure storage so a cold app start keeps the user signed
/// in, and any widget listening via [TokenStore]'s [ValueNotifier]
/// interface (typically through [AuthScope]) rebuilds when the token
/// changes.
///
/// Storage backends:
///   - iOS / macOS: Keychain
///   - Android:     EncryptedSharedPreferences
///   - Web:         WebCrypto-encrypted localStorage
///   - Linux:       libsecret (gnome-keyring / KWallet via Secret API)
///   - Windows:     Credential Locker
///
/// The token is intentionally never logged or rendered in the UI; only
/// the [isAuthenticated] flag is exposed as a public boolean.

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class TokenStore extends ValueNotifier<String?> {
  TokenStore._() : super(null);

  /// Process-wide singleton. Constructed lazily so unit tests that
  /// stub `flutter_secure_storage` can swap [_storage] before the
  /// first call to [load].
  static final TokenStore instance = TokenStore._();

  static const String _storageKey = 'devskel.access_token';

  static const FlutterSecureStorage _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  bool get isAuthenticated => value != null && value!.isNotEmpty;

  /// Hydrate the in-memory value from secure storage. Call this once
  /// during `main()` (after `WidgetsFlutterBinding.ensureInitialized`)
  /// before runApp so the very first frame already knows whether the
  /// user is signed in.
  Future<void> load() async {
    try {
      value = await _storage.read(key: _storageKey);
    } catch (_) {
      // Storage backends can throw on first launch (e.g. iOS Keychain
      // not yet provisioned). Treat as "no token yet" so the
      // LoginScreen renders normally.
      value = null;
    }
  }

  /// Persist a new token (or null to sign out). Notifies listeners
  /// inside the same [notifyListeners] call as setting [value], so a
  /// single rebuild flushes both the auth widget tree and the
  /// AppStateScope hydration effect.
  Future<void> setToken(String? token) async {
    value = token;
    try {
      if (token == null || token.isEmpty) {
        await _storage.delete(key: _storageKey);
      } else {
        await _storage.write(key: _storageKey, value: token);
      }
    } catch (_) {
      // Swallow storage errors here — the in-memory value is the
      // source of truth for the current session, and the next
      // successful login will overwrite the persisted blob anyway.
    }
  }

  Future<void> clear() => setToken(null);
}
