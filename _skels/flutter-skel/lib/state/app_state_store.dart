/// App-state pub/sub store.
///
/// Mirrors React's `src/state/app-state-store.ts`. Holds arbitrary
/// JSON-serialisable slices of state keyed by string (e.g.
/// `'items.showCompleted'`, `'sidebar.collapsed'`). Subscribers are
/// notified whenever a slice changes — the Flutter side wires this up
/// via [AppStateScope] + a small `useAppState`-style helper so any
/// widget reading a slice rebuilds automatically when another widget
/// (or the loader) writes a new value.
///
/// The store extends [ChangeNotifier] for the global "anything
/// changed" signal, and exposes per-key listeners through
/// [subscribeSlice] for callers that only care about a single slice.
///
/// The persistence layer (writing to the backend `/api/state`
/// endpoint) lives in `state_api.dart` + `app_state_scope.dart` so the
/// store itself stays simple and unit-testable without HTTP.

import 'package:flutter/foundation.dart';

typedef SliceListener = void Function(Object? next);

class AppStateStore extends ChangeNotifier {
  final Map<String, Object?> _data = <String, Object?>{};
  final Map<String, Set<SliceListener>> _sliceListeners =
      <String, Set<SliceListener>>{};

  /// Read a slice. Returns `null` when the slice is unknown.
  ///
  /// Uses an explicit cast inside the `is T` branch because dart2js
  /// (the Flutter Web compiler) does not promote `Object?` through a
  /// generic type test the way the analyzer does — without the cast
  /// the build fails with "A value of type 'Object' can't be returned
  /// from a function with return type 'T?'".
  T? getSlice<T>(String key) {
    final value = _data[key];
    if (value is T) {
      return value as T;
    }
    return null;
  }

  /// Write a slice and notify both the per-slice listeners and the
  /// global [ChangeNotifier] subscribers (so a [ListenableBuilder]
  /// listening to the whole store rebuilds too).
  void setSlice<T>(String key, T value) {
    _data[key] = value;
    _notifySlice(key, value);
    notifyListeners();
  }

  void deleteSlice(String key) {
    _data.remove(key);
    _notifySlice(key, null);
    notifyListeners();
  }

  /// Subscribe to changes for a single slice. Returns a callback that
  /// removes the listener — store this in a `StatefulWidget`'s
  /// dispose method to avoid leaks.
  VoidCallback subscribeSlice(String key, SliceListener listener) {
    final subs = _sliceListeners.putIfAbsent(key, () => <SliceListener>{});
    subs.add(listener);
    return () {
      subs.remove(listener);
    };
  }

  /// Replace the entire store with a fresh snapshot. Used by
  /// [AppStateScope] to hydrate from the backend on login. Notifies
  /// every relevant listener exactly once.
  void hydrate(Map<String, Object?> snapshot) {
    final allKeys = <String>{..._data.keys, ...snapshot.keys};
    _data
      ..clear()
      ..addAll(snapshot);
    for (final key in allKeys) {
      _notifySlice(key, _data[key]);
    }
    notifyListeners();
  }

  /// Drop every slice. Called by [AppStateScope] on logout so the next
  /// login starts from a clean slate.
  void reset() => hydrate(const <String, Object?>{});

  Map<String, Object?> snapshot() => Map<String, Object?>.unmodifiable(_data);

  void _notifySlice(String key, Object? value) {
    final subs = _sliceListeners[key];
    if (subs == null) return;
    // Iterate over a copy so a listener that unsubscribes itself
    // during the callback does not mutate the set we're walking.
    for (final listener in subs.toList(growable: false)) {
      listener(value);
    }
  }
}
