/// Frontend view of the wrapper-shared environment.
///
/// Loaded once at app startup via [AppConfig.load], which delegates to
/// `flutter_dotenv` to read the wrapper-level `<wrapper>/.env` file
/// that the gen script copies into this app's bundle as the `.env`
/// asset (see `pubspec.yaml`'s `flutter.assets` list).
///
/// To use a value at runtime, hold onto an [AppConfig] instance from
/// the widget tree (see `lib/main.dart`) — never reach into the
/// `dotenv` global directly from screens or controllers.
///
/// IMPORTANT: only frontend-safe values are exposed here. `JWT_SECRET`
/// is intentionally NOT loaded into [AppConfig] even though the
/// wrapper `.env` contains it — secrets do not belong in a mobile or
/// web app bundle.

import 'package:flutter_dotenv/flutter_dotenv.dart';

class JwtConfig {
  const JwtConfig({
    required this.algorithm,
    required this.issuer,
    required this.accessTtl,
    required this.refreshTtl,
  });

  final String algorithm;
  final String issuer;
  final int accessTtl;
  final int refreshTtl;
}

class AppConfig {
  const AppConfig({
    required this.backendUrl,
    required this.jwt,
    required this.services,
  });

  /// URL of the default backend the frontend should call. Comes from
  /// `BACKEND_URL` in `<wrapper>/.env`. Compose endpoints as
  /// `'${config.backendUrl}/api/...'`.
  ///
  /// Defaults to `http://localhost:8000` (the django-bolt convention)
  /// when `BACKEND_URL` is unset and no `SERVICE_URL_*` value is
  /// available.
  final String backendUrl;

  /// Public JWT claims so client code can render audit details
  /// (issuer, algorithm, TTL hints) without sniffing the token. The
  /// secret is intentionally absent.
  final JwtConfig jwt;

  /// Map of slugged service names → URLs (e.g.
  /// `services['ticket_service']` is `http://127.0.0.1:8001`).
  /// Populated from `SERVICE_URL_<SLUG>` entries written by
  /// `<wrapper>/_shared/service-urls.env` and merged into the wrapper
  /// `.env` by `common-wrapper.sh`.
  final Map<String, String> services;

  /// Load the wrapper-shared `.env` asset into a fresh [AppConfig].
  ///
  /// Must be awaited before runApp so the very first frame already has
  /// the resolved backend URL.
  static Future<AppConfig> load({String fileName = '.env'}) async {
    try {
      await dotenv.load(fileName: fileName);
    } catch (_) {
      // Missing `.env` is fine — every value falls back to the same
      // defaults the React skeleton uses, so a fresh `flutter run`
      // outside a wrapper still boots.
    }
    return AppConfig._fromEnv();
  }

  static AppConfig _fromEnv() {
    final services = _collectServiceUrls();
    final backendUrl = _resolveBackendUrl(services);
    return AppConfig(
      backendUrl: backendUrl,
      jwt: JwtConfig(
        algorithm: _readString('JWT_ALGORITHM', 'HS256'),
        issuer: _readString('JWT_ISSUER', 'devskel'),
        accessTtl: _readInt('JWT_ACCESS_TTL', 3600),
        refreshTtl: _readInt('JWT_REFRESH_TTL', 604800),
      ),
      services: services,
    );
  }

  /// Resolution order matches `vite.config.ts` in the React skeleton:
  ///
  /// 1. Explicit `BACKEND_URL` from the wrapper `.env`.
  /// 2. The first `SERVICE_URL_*` value (alphabetically) so a
  ///    backend-only wrapper still works without explicit config.
  /// 3. The django-bolt default `http://localhost:8000`.
  static String _resolveBackendUrl(Map<String, String> services) {
    final explicit = _readString('BACKEND_URL', '');
    if (explicit.isNotEmpty) return explicit;
    if (services.isNotEmpty) {
      final sortedKeys = services.keys.toList()..sort();
      return services[sortedKeys.first]!;
    }
    return 'http://localhost:8000';
  }

  static Map<String, String> _collectServiceUrls() {
    final out = <String, String>{};
    dotenv.env.forEach((key, value) {
      if (!key.startsWith('SERVICE_URL_')) return;
      if (value.isEmpty) return;
      out[key.substring('SERVICE_URL_'.length).toLowerCase()] = value;
    });
    return out;
  }

  static String _readString(String key, String fallback) {
    final value = dotenv.maybeGet(key);
    if (value == null || value.isEmpty) return fallback;
    return value;
  }

  static int _readInt(String key, int fallback) {
    final raw = _readString(key, '');
    if (raw.isEmpty) return fallback;
    return int.tryParse(raw) ?? fallback;
  }
}
