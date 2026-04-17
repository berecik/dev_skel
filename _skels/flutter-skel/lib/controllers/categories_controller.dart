/// `CategoriesController` — `ChangeNotifier`-backed view-model for the
/// categories list.
///
/// Mirrors [ItemsController]: holds a typed list, a loading flag, an
/// error string, and the boolean `unauthorized` signal that the
/// LoginScreen consumes. Auto-refreshes whenever the bearer token
/// changes (login or logout) by listening to the [TokenStore].
///
/// Mount one instance per app and pass it down via a
/// [ListenableBuilder] inside the screens that consume it. Calling
/// [refresh] or [create] mutates the in-memory cache and notifies
/// listeners exactly once per call so the rebuild story is predictable.

import 'package:flutter/foundation.dart';

import '../api/categories_client.dart';
import '../api/items_client.dart' show AuthError;
import '../auth/token_store.dart';

class CategoriesController extends ChangeNotifier {
  CategoriesController({
    required this.client,
    required this.tokenStore,
  }) {
    tokenStore.addListener(_onAuthChanged);
    if (tokenStore.isAuthenticated) {
      Future<void>.microtask(refresh);
    }
  }

  final CategoriesClient client;
  final TokenStore tokenStore;

  List<ItemCategory> _categories = const <ItemCategory>[];
  bool _loading = false;
  String? _error;
  bool _unauthorized = false;

  List<ItemCategory> get categories => _categories;
  bool get loading => _loading;
  String? get error => _error;
  bool get unauthorized => _unauthorized;

  Future<void> refresh() async {
    _loading = true;
    _error = null;
    _unauthorized = false;
    notifyListeners();
    try {
      final next = await client.listCategories();
      _categories = next;
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

  Future<ItemCategory> create(NewCategory payload) async {
    final created = await client.createCategory(payload);
    _categories = <ItemCategory>[created, ..._categories];
    notifyListeners();
    return created;
  }

  Future<ItemCategory> update(int id, NewCategory payload) async {
    final updated = await client.updateCategory(id, payload);
    _categories = <ItemCategory>[
      for (final cat in _categories)
        if (cat.id == id) updated else cat,
    ];
    notifyListeners();
    return updated;
  }

  Future<void> delete(int id) async {
    await client.deleteCategory(id);
    _categories = <ItemCategory>[
      for (final cat in _categories)
        if (cat.id != id) cat,
    ];
    notifyListeners();
  }

  void _onAuthChanged() {
    if (tokenStore.isAuthenticated) {
      refresh();
    } else {
      _categories = const <ItemCategory>[];
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
