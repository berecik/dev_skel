/// Typed order + catalog client.
///
/// Mirrors the items/categories client pattern. Talks to the
/// wrapper-shared `/api/catalog` and `/api/orders` endpoints exposed
/// by backends that ship the canonical orders contract. The base URL
/// comes from [AppConfig.backendUrl], which is loaded from
/// `<wrapper>/.env` via `flutter_dotenv` at startup.
///
/// Authentication: every request automatically attaches an
/// `Authorization: Bearer <token>` header when [TokenStore.value] is
/// non-null. Pass an explicit `token` argument to override the stored
/// value (useful in tests and inside the login flow itself).
///
/// 401 / 403 responses raise an [AuthError] (reused from
/// `items_client.dart`) so the UI can show a LoginScreen instead of
/// an error banner; every other non-2xx response raises a generic
/// [HttpException].

import 'dart:async';
import 'dart:convert';
import 'dart:io' show HttpException;

import 'package:http/http.dart' as http;

import '../auth/token_store.dart';
import '../config.dart';
import 'items_client.dart' show AuthError;

// ---------------------------------------------------------------------------
// Model classes
// ---------------------------------------------------------------------------

class CatalogItem {
  const CatalogItem({
    required this.id,
    required this.name,
    required this.description,
    required this.price,
    required this.category,
    required this.available,
  });

  final int id;
  final String name;
  final String description;
  final double price;
  final String category;
  final bool available;

  factory CatalogItem.fromJson(Map<String, dynamic> json) {
    return CatalogItem(
      id: json['id'] as int,
      name: (json['name'] ?? '') as String,
      description: (json['description'] ?? '') as String,
      price: (json['price'] as num).toDouble(),
      category: (json['category'] ?? '') as String,
      available: (json['available'] ?? true) as bool,
    );
  }
}

class Order {
  const Order({
    required this.id,
    required this.userId,
    required this.status,
    required this.createdAt,
    this.submittedAt,
    this.waitMinutes,
    this.feedback,
  });

  final int id;
  final int userId;
  final String status;
  final String createdAt;
  final String? submittedAt;
  final int? waitMinutes;
  final String? feedback;

  factory Order.fromJson(Map<String, dynamic> json) {
    return Order(
      id: json['id'] as int,
      userId: json['user_id'] as int,
      status: (json['status'] ?? '') as String,
      createdAt: (json['created_at'] ?? '') as String,
      submittedAt: json['submitted_at'] as String?,
      waitMinutes: json['wait_minutes'] as int?,
      feedback: json['feedback'] as String?,
    );
  }
}

class OrderLine {
  const OrderLine({
    required this.id,
    required this.catalogItemId,
    required this.quantity,
    required this.unitPrice,
  });

  final int id;
  final int catalogItemId;
  final int quantity;
  final double unitPrice;

  factory OrderLine.fromJson(Map<String, dynamic> json) {
    return OrderLine(
      id: json['id'] as int,
      catalogItemId: json['catalog_item_id'] as int,
      quantity: (json['quantity'] ?? 1) as int,
      unitPrice: (json['unit_price'] as num).toDouble(),
    );
  }
}

class OrderAddress {
  const OrderAddress({
    this.id,
    required this.street,
    required this.city,
    required this.zipCode,
    required this.phone,
    required this.notes,
  });

  final int? id;
  final String street;
  final String city;
  final String zipCode;
  final String phone;
  final String notes;

  factory OrderAddress.fromJson(Map<String, dynamic> json) {
    return OrderAddress(
      id: json['id'] as int?,
      street: (json['street'] ?? '') as String,
      city: (json['city'] ?? '') as String,
      zipCode: (json['zip_code'] ?? '') as String,
      phone: (json['phone'] ?? '') as String,
      notes: (json['notes'] ?? '') as String,
    );
  }
}

class OrderDetail extends Order {
  const OrderDetail({
    required super.id,
    required super.userId,
    required super.status,
    required super.createdAt,
    super.submittedAt,
    super.waitMinutes,
    super.feedback,
    required this.lines,
    this.address,
  });

  final List<OrderLine> lines;
  final OrderAddress? address;

  factory OrderDetail.fromJson(Map<String, dynamic> json) {
    final linesJson = (json['lines'] ?? <dynamic>[]) as List<dynamic>;
    final addressJson = json['address'] as Map<String, dynamic>?;
    return OrderDetail(
      id: json['id'] as int,
      userId: json['user_id'] as int,
      status: (json['status'] ?? '') as String,
      createdAt: (json['created_at'] ?? '') as String,
      submittedAt: json['submitted_at'] as String?,
      waitMinutes: json['wait_minutes'] as int?,
      feedback: json['feedback'] as String?,
      lines: linesJson
          .map((row) => OrderLine.fromJson(row as Map<String, dynamic>))
          .toList(growable: false),
      address:
          addressJson != null ? OrderAddress.fromJson(addressJson) : null,
    );
  }
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

class OrdersClient {
  OrdersClient({
    required this.config,
    required this.tokenStore,
    http.Client? client,
  }) : _client = client ?? http.Client();

  final AppConfig config;
  final TokenStore tokenStore;
  final http.Client _client;

  String get _catalogBase => '${config.backendUrl}/api/catalog';
  String get _ordersBase => '${config.backendUrl}/api/orders';

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

  // ── Catalog ──────────────────────────────────────────────────────

  Future<List<CatalogItem>> listCatalog({String? token}) async {
    final response = await _client.get(
      Uri.parse(_catalogBase),
      headers: _headers(token: token),
    );
    return _unwrap<List<CatalogItem>>(response, (body) {
      final List<dynamic> list;
      if (body is List<dynamic>) {
        list = body;
      } else if (body is Map<String, dynamic>) {
        list = (body['results'] ?? body['items'] ?? <dynamic>[]) as List<dynamic>;
      } else {
        list = <dynamic>[];
      }
      return list
          .map((row) => CatalogItem.fromJson(row as Map<String, dynamic>))
          .toList(growable: false);
    });
  }

  Future<CatalogItem> createCatalogItem({
    required String name,
    required double price,
    String category = '',
    String description = '',
    bool available = true,
    String? token,
  }) async {
    final response = await _client.post(
      Uri.parse(_catalogBase),
      headers: _headers(token: token, json: true),
      body: jsonEncode(<String, dynamic>{
        'name': name,
        'price': price,
        'category': category,
        'description': description,
        'available': available,
      }),
    );
    return _unwrap<CatalogItem>(
      response,
      (body) => CatalogItem.fromJson(body as Map<String, dynamic>),
    );
  }

  // ── Orders ───────────────────────────────────────────────────────

  Future<Order> createOrder({String? token}) async {
    final response = await _client.post(
      Uri.parse(_ordersBase),
      headers: _headers(token: token, json: true),
      body: jsonEncode(<String, dynamic>{}),
    );
    return _unwrap<Order>(
      response,
      (body) => Order.fromJson(body as Map<String, dynamic>),
    );
  }

  Future<List<Order>> listOrders({String? token}) async {
    final response = await _client.get(
      Uri.parse(_ordersBase),
      headers: _headers(token: token),
    );
    return _unwrap<List<Order>>(response, (body) {
      final List<dynamic> list;
      if (body is List<dynamic>) {
        list = body;
      } else if (body is Map<String, dynamic>) {
        list = (body['results'] ?? body['orders'] ?? <dynamic>[]) as List<dynamic>;
      } else {
        list = <dynamic>[];
      }
      return list
          .map((row) => Order.fromJson(row as Map<String, dynamic>))
          .toList(growable: false);
    });
  }

  Future<OrderDetail> getOrder(int id, {String? token}) async {
    final response = await _client.get(
      Uri.parse('$_ordersBase/$id'),
      headers: _headers(token: token),
    );
    return _unwrap<OrderDetail>(
      response,
      (body) => OrderDetail.fromJson(body as Map<String, dynamic>),
    );
  }

  Future<OrderLine> addLine(
    int orderId, {
    required int catalogItemId,
    int quantity = 1,
    String? token,
  }) async {
    final response = await _client.post(
      Uri.parse('$_ordersBase/$orderId/lines'),
      headers: _headers(token: token, json: true),
      body: jsonEncode(<String, dynamic>{
        'catalog_item_id': catalogItemId,
        'quantity': quantity,
      }),
    );
    return _unwrap<OrderLine>(
      response,
      (body) => OrderLine.fromJson(body as Map<String, dynamic>),
    );
  }

  Future<void> removeLine(int orderId, int lineId, {String? token}) async {
    final response = await _client.delete(
      Uri.parse('$_ordersBase/$orderId/lines/$lineId'),
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

  Future<void> setAddress(
    int orderId, {
    required String street,
    required String city,
    required String zipCode,
    String phone = '',
    String notes = '',
    String? token,
  }) async {
    final response = await _client.put(
      Uri.parse('$_ordersBase/$orderId/address'),
      headers: _headers(token: token, json: true),
      body: jsonEncode(<String, dynamic>{
        'street': street,
        'city': city,
        'zip_code': zipCode,
        'phone': phone,
        'notes': notes,
      }),
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

  Future<Order> submitOrder(int orderId, {String? token}) async {
    final response = await _client.post(
      Uri.parse('$_ordersBase/$orderId/submit'),
      headers: _headers(token: token),
    );
    return _unwrap<Order>(
      response,
      (body) => Order.fromJson(body as Map<String, dynamic>),
    );
  }

  Future<Order> approveOrder(
    int orderId, {
    required int waitMinutes,
    required String feedback,
    String? token,
  }) async {
    final response = await _client.post(
      Uri.parse('$_ordersBase/$orderId/approve'),
      headers: _headers(token: token, json: true),
      body: jsonEncode(<String, dynamic>{
        'wait_minutes': waitMinutes,
        'feedback': feedback,
      }),
    );
    return _unwrap<Order>(
      response,
      (body) => Order.fromJson(body as Map<String, dynamic>),
    );
  }

  Future<Order> rejectOrder(
    int orderId, {
    required String feedback,
    String? token,
  }) async {
    final response = await _client.post(
      Uri.parse('$_ordersBase/$orderId/reject'),
      headers: _headers(token: token, json: true),
      body: jsonEncode(<String, dynamic>{
        'feedback': feedback,
      }),
    );
    return _unwrap<Order>(
      response,
      (body) => Order.fromJson(body as Map<String, dynamic>),
    );
  }

  void close() => _client.close();
}
