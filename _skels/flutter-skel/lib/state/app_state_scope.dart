/// `AppStateScope` — top-level wrapper that hydrates the app-state
/// store from the backend on login and clears it on logout.
///
/// Mirrors React's `AppStateProvider.tsx`. Mount this once inside the
/// authenticated branch of the widget tree (typically right above the
/// `HomeScreen`) and any descendant widget can call
/// `AppStateScope.of(context)` to read/write a persisted UI slice.
///
/// The scope deliberately does NOT cache hydration across logins:
/// each user has their own state, and switching accounts must reset
/// the store cleanly so the new user does not see the previous user's
/// preferences.

import 'package:flutter/widgets.dart';

import '../api/items_client.dart' show AuthError;
import '../auth/token_store.dart';
import 'app_state_store.dart';
import 'state_api.dart';

class AppStateScope extends StatefulWidget {
  const AppStateScope({
    super.key,
    required this.store,
    required this.tokenStore,
    required this.stateApi,
    required this.child,
  });

  final AppStateStore store;
  final TokenStore tokenStore;
  final StateApi stateApi;
  final Widget child;

  /// Look up the [AppStateStore] from the nearest ancestor scope.
  static AppStateStore of(BuildContext context) {
    final scope =
        context.dependOnInheritedWidgetOfExactType<_AppStateInherited>();
    assert(scope != null, 'No AppStateScope found in widget tree');
    return scope!.notifier!;
  }

  /// Look up the [StateApi] (used by `useAppState`-style helpers that
  /// want to fire-and-forget a `saveState` call after writing to the
  /// in-memory store).
  static StateApi apiOf(BuildContext context) {
    final scope =
        context.getElementForInheritedWidgetOfExactType<_AppStateInherited>()
            ?.widget as _AppStateInherited?;
    assert(scope != null, 'No AppStateScope found in widget tree');
    return scope!.stateApi;
  }

  @override
  State<AppStateScope> createState() => _AppStateScopeState();
}

class _AppStateScopeState extends State<AppStateScope> {
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    widget.tokenStore.addListener(_onAuthChanged);
    if (widget.tokenStore.isAuthenticated) {
      _hydrate();
    }
  }

  @override
  void didUpdateWidget(covariant AppStateScope oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.tokenStore != widget.tokenStore) {
      oldWidget.tokenStore.removeListener(_onAuthChanged);
      widget.tokenStore.addListener(_onAuthChanged);
    }
  }

  @override
  void dispose() {
    widget.tokenStore.removeListener(_onAuthChanged);
    super.dispose();
  }

  void _onAuthChanged() {
    if (!mounted) return;
    if (widget.tokenStore.isAuthenticated) {
      _hydrate();
    } else {
      widget.store.reset();
      setState(() {
        _loading = false;
        _error = null;
      });
    }
  }

  Future<void> _hydrate() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final snapshot = await widget.stateApi.loadAllState();
      if (!mounted) return;
      widget.store.hydrate(snapshot);
    } on AuthError {
      // Stale token — clear it so the LoginScreen takes over.
      await widget.tokenStore.clear();
    } catch (err) {
      if (!mounted) return;
      setState(() {
        _error = err.toString();
      });
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return _AppStateInherited(
      notifier: widget.store,
      stateApi: widget.stateApi,
      loading: _loading,
      error: _error,
      child: widget.child,
    );
  }
}

class _AppStateInherited extends InheritedNotifier<AppStateStore> {
  const _AppStateInherited({
    required AppStateStore notifier,
    required this.stateApi,
    required this.loading,
    required this.error,
    required super.child,
  }) : super(notifier: notifier);

  final StateApi stateApi;
  final bool loading;
  final String? error;

  @override
  bool updateShouldNotify(covariant _AppStateInherited oldWidget) {
    return loading != oldWidget.loading ||
        error != oldWidget.error ||
        notifier != oldWidget.notifier;
  }
}

/// Convenience helper that mirrors React's `useAppState` hook: read a
/// slice with a default, and get a setter that updates the in-memory
/// store AND fires a `saveState` against the backend.
///
/// Call inside a `StatefulWidget`'s `build` method via the [context]:
///
/// ```dart
/// final state = readAppState<bool>(context, 'items.showCompleted', defaultValue: true);
/// state.set(true);  // updates store + persists
/// ```
class AppStateBinding<T> {
  AppStateBinding._(this._store, this._api, this._key, this._default);

  final AppStateStore _store;
  final StateApi _api;
  final String _key;
  final T _default;

  T get value {
    final current = _store.getSlice<T>(_key);
    return current ?? _default;
  }

  void set(T next) {
    _store.setSlice<T>(_key, next);
    // Fire-and-forget — production apps should surface errors via a
    // toast / retry queue, but the skeleton keeps it minimal.
    _api.saveState(_key, next).catchError((Object _) {});
  }
}

AppStateBinding<T> readAppState<T>(
  BuildContext context,
  String key, {
  required T defaultValue,
}) {
  final store = AppStateScope.of(context);
  final api = AppStateScope.apiOf(context);
  return AppStateBinding<T>._(store, api, key, defaultValue);
}
