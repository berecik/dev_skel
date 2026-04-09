/// Typed client for the wrapper-shared `/api/state` endpoints.
///
/// Mirrors React's `src/state/state-api.ts`. The default backend
/// (django-bolt) exposes:
///
///   GET    /api/state          → returns `{key: jsonString}` for the
///                                 current user (every slice).
///   PUT    /api/state/<key>    → upserts a single slice; body is
///                                 `{"value": "<json string>"}`.
///   DELETE /api/state/<key>    → drops a single slice.
///
/// Every request is JWT-protected via the wrapper-shared bearer token
/// (see `lib/auth/token_store.dart`). Other backends (django, fastapi,
/// flask, ...) can implement the same contract — see the docs.
///
/// The `value` payload on the wire is a JSON string so the backend
/// never has to parse it; this module handles the encode/decode for
/// the Flutter side.

import 'dart:convert';
import 'dart:io' show HttpException;

import 'package:http/http.dart' as http;

import '../api/items_client.dart' show AuthError;
import '../auth/token_store.dart';
import '../config.dart';

class StateApi {
  StateApi({
    required this.config,
    required this.tokenStore,
    http.Client? client,
  }) : _client = client ?? http.Client();

  final AppConfig config;
  final TokenStore tokenStore;
  final http.Client _client;

  String get _stateBase => '${config.backendUrl}/api/state';

  Map<String, String> _headers({String? token, bool json = false}) {
    final headers = <String, String>{};
    if (json) headers['Content-Type'] = 'application/json';
    final resolved = token ?? tokenStore.value;
    if (resolved != null && resolved.isNotEmpty) {
      headers['Authorization'] = 'Bearer $resolved';
    }
    return headers;
  }

  void _checkStatus(http.Response response) {
    if (response.statusCode == 401 || response.statusCode == 403) {
      throw AuthError('HTTP ${response.statusCode}: authentication required');
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw HttpException('HTTP ${response.statusCode}: ${response.body}');
    }
  }

  /// Load every state slice for the current user. Returns a map keyed
  /// by slice name with already-decoded values.
  ///
  /// The wire format stores values as JSON strings (so the backend
  /// never has to know the shape); this function `jsonDecode`s each
  /// one and silently drops slices that fail to parse so a corrupted
  /// slice does not block the rest of the cache from loading.
  Future<Map<String, Object?>> loadAllState({String? token}) async {
    final response = await _client.get(
      Uri.parse(_stateBase),
      headers: _headers(token: token),
    );
    _checkStatus(response);
    if (response.body.isEmpty) return const <String, Object?>{};
    final raw = jsonDecode(response.body) as Map<String, dynamic>;
    final decoded = <String, Object?>{};
    raw.forEach((key, value) {
      if (value is! String) return;
      try {
        decoded[key] = jsonDecode(value);
      } catch (_) {
        // Skip slices that aren't valid JSON — they were probably
        // written by a different version of the app and will be
        // overwritten on the next save.
      }
    });
    return decoded;
  }

  /// Upsert a single slice. The value is JSON-stringified before being
  /// sent so the backend never has to know its shape.
  Future<void> saveState(String key, Object? value, {String? token}) async {
    final response = await _client.put(
      Uri.parse('$_stateBase/${Uri.encodeComponent(key)}'),
      headers: _headers(token: token, json: true),
      body: jsonEncode({'value': jsonEncode(value)}),
    );
    _checkStatus(response);
  }

  /// Drop a single slice.
  Future<void> deleteState(String key, {String? token}) async {
    final response = await _client.delete(
      Uri.parse('$_stateBase/${Uri.encodeComponent(key)}'),
      headers: _headers(token: token),
    );
    _checkStatus(response);
  }

  void close() => _client.close();
}
