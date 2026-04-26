/// `OrdersController` — `ChangeNotifier`-backed view-model for the
/// orders list.
///
/// Mirrors [ItemsController] / [CategoriesController]: holds a typed
/// list, a loading flag, an error string, and the boolean
/// `unauthorized` signal that the LoginScreen consumes. Auto-refreshes
/// whenever the bearer token changes (login or logout) by listening to
/// the [TokenStore].
///
/// Mount one instance per app and pass it down via a
/// [ListenableBuilder] inside the screens that consume it. Calling
/// [refresh], [createOrder], [submitOrder], [approveOrder], or
/// [rejectOrder] mutates the in-memory cache and notifies listeners
/// exactly once per call so the rebuild story is predictable.

import 'package:flutter/foundation.dart';

import '../api/items_client.dart' show AuthError;
import '../api/orders_client.dart';
import '../auth/token_store.dart';

class OrdersController extends ChangeNotifier {
  OrdersController({
    required this.client,
    required this.tokenStore,
  }) {
    tokenStore.addListener(_onAuthChanged);
    if (tokenStore.isAuthenticated) {
      Future<void>.microtask(refresh);
    }
  }

  final OrdersClient client;
  final TokenStore tokenStore;

  List<Order> _orders = const <Order>[];
  bool _loading = false;
  String? _error;
  bool _unauthorized = false;

  List<Order> get orders => _orders;
  bool get loading => _loading;
  String? get error => _error;
  bool get unauthorized => _unauthorized;

  /// Re-fetch the list explicitly (e.g. on a manual refresh button or
  /// after a login). Surfaces 401s through [unauthorized] and clears
  /// the stale token automatically.
  Future<void> refresh() async {
    _loading = true;
    _error = null;
    _unauthorized = false;
    notifyListeners();
    try {
      final next = await client.listOrders();
      _orders = next;
    } on AuthError {
      _unauthorized = true;
      await tokenStore.clear();
    } catch (err) {
      _error = err.toString();
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  /// Create a new (draft) order via the client and merge it into the
  /// local cache (newest first). Returns the created order so callers
  /// can chain additional UX.
  Future<Order> createOrder() async {
    final created = await client.createOrder();
    _orders = <Order>[created, ..._orders];
    notifyListeners();
    return created;
  }

  /// Fetch the full detail (lines + address) for a single order.
  Future<OrderDetail> getDetail(int id) async {
    return client.getOrder(id);
  }

  /// Add a line to an order. Returns the created line.
  Future<OrderLine> addLine(
    int orderId, {
    required int catalogItemId,
    int quantity = 1,
  }) async {
    return client.addLine(
      orderId,
      catalogItemId: catalogItemId,
      quantity: quantity,
    );
  }

  /// Submit a draft order. Replaces the order in the local cache.
  Future<Order> submitOrder(int orderId) async {
    final updated = await client.submitOrder(orderId);
    _orders = <Order>[
      for (final order in _orders)
        if (order.id == orderId) updated else order,
    ];
    notifyListeners();
    return updated;
  }

  /// Approve a submitted order. Replaces the order in the local cache.
  Future<Order> approveOrder(
    int orderId, {
    required int waitMinutes,
    required String feedback,
  }) async {
    final updated = await client.approveOrder(
      orderId,
      waitMinutes: waitMinutes,
      feedback: feedback,
    );
    _orders = <Order>[
      for (final order in _orders)
        if (order.id == orderId) updated else order,
    ];
    notifyListeners();
    return updated;
  }

  /// Reject a submitted order. Replaces the order in the local cache.
  Future<Order> rejectOrder(
    int orderId, {
    required String feedback,
  }) async {
    final updated = await client.rejectOrder(
      orderId,
      feedback: feedback,
    );
    _orders = <Order>[
      for (final order in _orders)
        if (order.id == orderId) updated else order,
    ];
    notifyListeners();
    return updated;
  }

  void _onAuthChanged() {
    if (tokenStore.isAuthenticated) {
      refresh();
    } else {
      _orders = const <Order>[];
      _loading = false;
      _error = null;
      notifyListeners();
    }
  }

  @override
  void dispose() {
    tokenStore.removeListener(_onAuthChanged);
    super.dispose();
  }
}
