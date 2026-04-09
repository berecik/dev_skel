/// `AuthScope` — `InheritedNotifier` wrapper around [TokenStore].
///
/// Mirrors React's `useAuthToken` custom hook in a Flutter-idiomatic
/// way: descendants call `AuthScope.of(context)` to read the current
/// token (or just whether the user is authenticated), and the
/// framework rebuilds them when the underlying [ValueNotifier]
/// notifies. No third-party state-management dep — Flutter ships
/// `InheritedNotifier` exactly for this pattern.
///
/// Mount [AuthScope] once near the root of the widget tree (above
/// [MaterialApp]) and pass [TokenStore.instance] as the notifier.

import 'package:flutter/widgets.dart';

import 'token_store.dart';

class AuthScope extends InheritedNotifier<TokenStore> {
  const AuthScope({
    super.key,
    required TokenStore store,
    required super.child,
  }) : super(notifier: store);

  /// Look up the [TokenStore] from the nearest ancestor [AuthScope].
  ///
  /// Throws if no [AuthScope] is mounted — the test widget pumps an
  /// [AuthScope] explicitly, so this assertion catches misuse early.
  static TokenStore of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AuthScope>();
    assert(scope != null, 'No AuthScope found in widget tree');
    return scope!.notifier!;
  }

  /// Non-listening variant for callbacks (e.g. event handlers) that
  /// just need the current value without subscribing to changes.
  static TokenStore read(BuildContext context) {
    final scope =
        context.getElementForInheritedWidgetOfExactType<AuthScope>()?.widget
            as AuthScope?;
    assert(scope != null, 'No AuthScope found in widget tree');
    return scope!.notifier!;
  }
}
