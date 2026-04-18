/// Typed item repository client.
///
/// Mirrors React's `src/api/items.ts`. Talks to the wrapper-shared
/// `/api/items` endpoint exposed by every dev_skel backend that ships
/// the canonical contract (django-bolt and fastapi out of the box).
/// The base URL comes from [AppConfig.backendUrl], which is loaded
/// from `<wrapper>/.env` via `flutter_dotenv` at startup.
///
/// Authentication: every request automatically attaches an
/// `Authorization: Bearer <token>` header when [TokenStore.value] is
/// non-null. Pass an explicit `token` argument to override the stored
/// value (useful in tests and inside the login flow itself, where the
/// new token is not yet in the store when the very first authenticated
/// call goes out).
///
/// 401 / 403 responses raise an [AuthError] so the UI can show a
/// LoginScreen instead of an error banner; every other non-2xx
/// response raises a generic [HttpException].

import 'dart:async';
import 'dart:convert';
import 'dart:io' show HttpException;

import 'package:http/http.dart' as http;

import '../auth/token_store.dart';
import '../config.dart';

class Item {
  const Item({
    required this.id,
    required this.name,
    required this.description,
    required this.isCompleted,
    required this.createdAt,
    required this.updatedAt,
    this.categoryId,
  });

  final int id;
  final String name;
  final String? description;
  final bool isCompleted;
  final String createdAt;
  final String updatedAt;
  final int? categoryId;

  factory Item.fromJson(Map<String, dynamic> json) {
    return Item(
      id: json['id'] as int,
      name: (json['name'] ?? '') as String,
      description: json['description'] as String?,
      isCompleted: (json['is_completed'] ?? false) as bool,
      createdAt: (json['created_at'] ?? '') as String,
      updatedAt: (json['updated_at'] ?? '') as String,
      categoryId: json['category_id'] as int?,
    );
  }
}

class NewItem {
  const NewItem({
    required this.name,
    this.description,
    this.isCompleted,
    this.categoryId,
  });

  final String name;
  final String? description;
  final bool? isCompleted;
  final int? categoryId;

  Map<String, dynamic> toJson() {
    final out = <String, dynamic>{'name': name};
    if (description != null) out['description'] = description;
    if (isCompleted != null) out['is_completed'] = isCompleted;
    if (categoryId != null) out['category_id'] = categoryId;
    return out;
  }
}

/// 401 / 403 responses get their own exception class so the UI can
/// render a LoginScreen instead of an error banner.
class AuthError implements Exception {
  const AuthError([this.message = 'Authentication required']);
  final String message;
  @override
  String toString() => 'AuthError: $message';
}

class ItemsClient {
  ItemsClient({
    required this.config,
    required this.tokenStore,
    http.Client? client,
  }) : _client = client ?? http.Client();

  final AppConfig config;
  final TokenStore tokenStore;
  final http.Client _client;

  String get _itemsBase => '${config.backendUrl}/api/items';

  /// Build the request headers with the optional Bearer token. When
  /// [token] is the special sentinel value of `''` (empty string),
  /// no Authorization header is set even if the store has a value —
  /// useful for the login endpoint, which must NOT carry a stale token.
  Map<String, String> _headers({String? token, bool json = false}) {
    final headers = <String, String>{};
    if (json) headers['Content-Type'] = 'application/json';
    final resolved = token ?? tokenStore.value;
    if (resolved != null && resolved.isNotEmpty) {
      headers['Authorization'] = 'Bearer $resolved';
    }
    return headers;
  }

  Future<T> _unwrap<T>(http.Response response, T Function(dynamic body) parse) async {
    if (response.statusCode == 401 || response.statusCode == 403) {
      throw AuthError('HTTP ${response.statusCode}: authentication required');
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw HttpException(
        'HTTP ${response.statusCode}: ${response.body}',
      );
    }
    if (response.body.isEmpty) return parse(null);
    return parse(jsonDecode(response.body));
  }

  Future<List<Item>> listItems({String? token}) async {
    final response = await _client.get(
      Uri.parse(_itemsBase),
      headers: _headers(token: token),
    );
    return _unwrap<List<Item>>(response, (body) {
      // Handle both raw arrays and paginated wrappers
      // ({results: [...]}, {items: [...]})
      final List<dynamic> list;
      if (body is List<dynamic>) {
        list = body;
      } else if (body is Map<String, dynamic>) {
        list = (body['results'] ?? body['items'] ?? <dynamic>[]) as List<dynamic>;
      } else {
        list = <dynamic>[];
      }
      return list
          .map((row) => Item.fromJson(row as Map<String, dynamic>))
          .toList(growable: false);
    });
  }

  Future<Item> getItem(int id, {String? token}) async {
    final response = await _client.get(
      Uri.parse('$_itemsBase/$id'),
      headers: _headers(token: token),
    );
    return _unwrap<Item>(response, (body) => Item.fromJson(body as Map<String, dynamic>));
  }

  Future<Item> createItem(NewItem payload, {String? token}) async {
    final response = await _client.post(
      Uri.parse(_itemsBase),
      headers: _headers(token: token, json: true),
      body: jsonEncode(payload.toJson()),
    );
    return _unwrap<Item>(response, (body) => Item.fromJson(body as Map<String, dynamic>));
  }

  Future<Item> completeItem(int id, {String? token}) async {
    final response = await _client.post(
      Uri.parse('$_itemsBase/$id/complete'),
      headers: _headers(token: token),
    );
    return _unwrap<Item>(response, (body) => Item.fromJson(body as Map<String, dynamic>));
  }

  /// POST username + password to the wrapper-shared `/api/auth/login`
  /// endpoint and return the access token.
  ///
  /// The endpoint shape matches the canonical dev_skel response
  /// (`{access, refresh, user_id, username}`); we tolerate `token` as
  /// a fallback so older backends still work, mirroring React's
  /// behaviour.
  Future<String> loginWithPassword(String username, String password) async {
    final response = await _client.post(
      Uri.parse('${config.backendUrl}/api/auth/login'),
      headers: const {'Content-Type': 'application/json'},
      // Pass an empty token to skip the Bearer header — the login
      // request must not carry a stale token.
      body: jsonEncode({'username': username, 'password': password}),
    );
    if (response.statusCode == 401) {
      throw const AuthError('Invalid credentials');
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw HttpException('HTTP ${response.statusCode}: ${response.body}');
    }
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final token = (body['access'] ?? body['token']) as String?;
    if (token == null || token.isEmpty) {
      throw const HttpException('Login response did not include an access token');
    }
    return token;
  }

  void close() => _client.close();
}
