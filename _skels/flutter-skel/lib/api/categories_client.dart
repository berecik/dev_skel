/// Typed category repository client.
///
/// Mirrors the items client pattern. Talks to the wrapper-shared
/// `/api/categories` endpoint exposed by backends that ship the
/// canonical categories contract. The base URL comes from
/// [AppConfig.backendUrl], which is loaded from `<wrapper>/.env` via
/// `flutter_dotenv` at startup.
///
/// Authentication: every request automatically attaches an
/// `Authorization: Bearer <token>` header when [TokenStore.value] is
/// non-null. Pass an explicit `token` argument to override the stored
/// value (useful in tests and inside the login flow itself).
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
import 'items_client.dart' show AuthError;

class ItemCategory {
  const ItemCategory({
    required this.id,
    required this.name,
    this.description,
    required this.createdAt,
    required this.updatedAt,
  });

  final int id;
  final String name;
  final String? description;
  final String createdAt;
  final String updatedAt;

  factory ItemCategory.fromJson(Map<String, dynamic> json) {
    return ItemCategory(
      id: json['id'] as int,
      name: (json['name'] ?? '') as String,
      description: json['description'] as String?,
      createdAt: (json['created_at'] ?? '') as String,
      updatedAt: (json['updated_at'] ?? '') as String,
    );
  }
}

class NewCategory {
  const NewCategory({
    required this.name,
    this.description,
  });

  final String name;
  final String? description;

  Map<String, dynamic> toJson() {
    final out = <String, dynamic>{'name': name};
    if (description != null) out['description'] = description;
    return out;
  }
}

class CategoriesClient {
  CategoriesClient({
    required this.config,
    required this.tokenStore,
    http.Client? client,
  }) : _client = client ?? http.Client();

  final AppConfig config;
  final TokenStore tokenStore;
  final http.Client _client;

  String get _categoriesBase => '${config.backendUrl}/api/categories';

  /// Build the request headers with the optional Bearer token.
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

  Future<List<ItemCategory>> listCategories({String? token}) async {
    final response = await _client.get(
      Uri.parse(_categoriesBase),
      headers: _headers(token: token),
    );
    return _unwrap<List<ItemCategory>>(response, (body) {
      final list = body as List<dynamic>;
      return list
          .map((row) => ItemCategory.fromJson(row as Map<String, dynamic>))
          .toList(growable: false);
    });
  }

  Future<ItemCategory> getCategory(int id, {String? token}) async {
    final response = await _client.get(
      Uri.parse('$_categoriesBase/$id'),
      headers: _headers(token: token),
    );
    return _unwrap<ItemCategory>(response, (body) => ItemCategory.fromJson(body as Map<String, dynamic>));
  }

  Future<ItemCategory> createCategory(NewCategory payload, {String? token}) async {
    final response = await _client.post(
      Uri.parse(_categoriesBase),
      headers: _headers(token: token, json: true),
      body: jsonEncode(payload.toJson()),
    );
    return _unwrap<ItemCategory>(response, (body) => ItemCategory.fromJson(body as Map<String, dynamic>));
  }

  Future<ItemCategory> updateCategory(int id, NewCategory payload, {String? token}) async {
    final response = await _client.put(
      Uri.parse('$_categoriesBase/$id'),
      headers: _headers(token: token, json: true),
      body: jsonEncode(payload.toJson()),
    );
    return _unwrap<ItemCategory>(response, (body) => ItemCategory.fromJson(body as Map<String, dynamic>));
  }

  Future<void> deleteCategory(int id, {String? token}) async {
    final response = await _client.delete(
      Uri.parse('$_categoriesBase/$id'),
      headers: _headers(token: token),
    );
    if (response.statusCode == 401 || response.statusCode == 403) {
      throw AuthError('HTTP ${response.statusCode}: authentication required');
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw HttpException(
        'HTTP ${response.statusCode}: ${response.body}',
      );
    }
  }

  void close() => _client.close();
}
