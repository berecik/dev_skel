/// `ItemsController` — `ChangeNotifier`-backed view-model for the
/// canonical items list.
///
/// Mirrors React's `useItems` custom hook: holds a typed list, a
/// loading flag, an error string, and the boolean `unauthorized`
/// signal that the LoginScreen consumes. Auto-refreshes whenever the
/// bearer token changes (login or logout) by listening to the
/// [TokenStore].
///
/// Mount one instance per app and pass it down via a
/// [ListenableBuilder] inside the screens that consume it. Calling
/// [refresh], [create], or [complete] mutates the in-memory cache and
/// notifies listeners exactly once per call so the rebuild story is
/// predictable.

import 'package:flutter/foundation.dart';

import '../api/items_client.dart';
import '../auth/token_store.dart';

class ItemsController extends ChangeNotifier {
  ItemsController({
    required this.client,
    required this.tokenStore,
  }) {
    tokenStore.addListener(_onAuthChanged);
    if (tokenStore.isAuthenticated) {
      // Trigger an initial fetch on the next microtask so callers
      // that subscribe right after construction still see the
      // notifyListeners() that follows the request.
      Future<void>.microtask(refresh);
    }
  }

  final ItemsClient client;
  final TokenStore tokenStore;

  List<Item> _items = const <Item>[];
  bool _loading = false;
  String? _error;
  bool _unauthorized = false;

  List<Item> get items => _items;
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
      final next = await client.listItems();
      _items = next;
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

  /// Create a new item via the client and merge it into the local
  /// cache (newest first). Returns the created item so callers can
  /// chain additional UX (toasts, scroll-to-new-row, ...).
  Future<Item> create(NewItem payload) async {
    final created = await client.createItem(payload);
    _items = <Item>[created, ..._items];
    notifyListeners();
    return created;
  }

  /// Mark an item complete and replace it in the local cache.
  Future<Item> complete(int id) async {
    final updated = await client.completeItem(id);
    _items = <Item>[
      for (final item in _items)
        if (item.id == id) updated else item,
    ];
    notifyListeners();
    return updated;
  }

  void _onAuthChanged() {
    if (tokenStore.isAuthenticated) {
      // Login (or token refresh) — re-fetch the list.
      refresh();
    } else {
      // Logout — drop the cache so the next login does not flash
      // stale data while the new fetch lands.
      _items = const <Item>[];
      _loading = false;
      _error = null;
      _unauthorized = false;
      notifyListeners();
    }
  }

  @override
  void dispose() {
    tokenStore.removeListener(_onAuthChanged);
    super.dispose();
  }
}
