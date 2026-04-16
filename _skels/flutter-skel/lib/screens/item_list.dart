/// `ItemListView` — renders the items returned by [ItemsController]
/// with a "Mark complete" button per row, plus a "show completed"
/// filter that **persists across reloads** via the wrapper-shared
/// `/api/state` endpoint.
///
/// Mirrors React's `ItemList.tsx`. The persistent filter is the
/// canonical demo of the Flutter state-management layer:
///
/// ```dart
/// final binding = readAppState<bool>(
///   context, 'items.showCompleted', defaultValue: true,
/// );
/// ```
///
/// `binding.set(...)` updates the in-memory store and fires off a
/// `saveState` against the backend so the filter survives a cold
/// app restart.

import 'package:flutter/material.dart';

import '../api/items_client.dart';
import '../controllers/items_controller.dart';
import '../state/app_state_scope.dart';

class ItemListView extends StatelessWidget {
  const ItemListView({super.key, required this.controller});

  final ItemsController controller;

  @override
  Widget build(BuildContext context) {
    final store = AppStateScope.of(context);

    return ListenableBuilder(
      listenable: Listenable.merge(<Listenable>[controller, store]),
      builder: (context, _) {
        final binding = readAppState<bool>(
          context,
          'items.showCompleted',
          defaultValue: true,
        );
        final showCompleted = binding.value;
        final items = controller.items;
        final visible = showCompleted
            ? items
            : items.where((Item item) => !item.isCompleted).toList(growable: false);

        if (controller.loading && items.isEmpty) {
          return const Padding(
            padding: EdgeInsets.all(24),
            child: Center(child: CircularProgressIndicator()),
          );
        }

        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                children: <Widget>[
                  Expanded(
                    child: Text(
                      visible.length == items.length
                          ? 'Items (${visible.length})'
                          : 'Items (${visible.length} of ${items.length})',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      const Text('Show completed'),
                      Switch(
                        value: showCompleted,
                        onChanged: binding.set,
                      ),
                      IconButton(
                        tooltip: 'Refresh',
                        icon: const Icon(Icons.refresh),
                        onPressed:
                            controller.loading ? null : controller.refresh,
                      ),
                    ],
                  ),
                ],
              ),
            ),
            if (controller.error != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Text(
                  'Error: ${controller.error}',
                  style:
                      TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            if (visible.isEmpty)
              Padding(
                padding: const EdgeInsets.all(24),
                child: Text(
                  items.isEmpty
                      ? 'No items yet — create one above.'
                      : 'No items match the current filter.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              )
            else
              // Bare `ListView.separated` (no `Flexible` / `Expanded`
              // wrapper). HomeScreen mounts ItemListView inside a
              // `SingleChildScrollView`, which gives this Column an
              // unbounded vertical extent. `Flexible` requires a
              // bounded parent and would explode with a layout error;
              // `shrinkWrap: true` + `NeverScrollableScrollPhysics`
              // lets the inner list size itself to its children and
              // delegate the actual scrolling to the outer
              // SingleChildScrollView.
              ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: visible.length,
                separatorBuilder: (_, __) => const Divider(height: 1),
                itemBuilder: (context, index) {
                  final item = visible[index];
                  return ListTile(
                    title: Text(
                      item.name,
                      style: TextStyle(
                        decoration: item.isCompleted
                            ? TextDecoration.lineThrough
                            : null,
                      ),
                    ),
                    subtitle: item.description == null
                        ? Text('updated ${item.updatedAt}')
                        : Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              Text(item.description!),
                              Text('updated ${item.updatedAt}'),
                            ],
                          ),
                    trailing: item.isCompleted
                        ? const Chip(label: Text('✓ done'))
                        : TextButton(
                            onPressed: () => controller.complete(item.id),
                            child: const Text('Mark complete'),
                          ),
                  );
                },
              ),
          ],
        );
      },
    );
  }
}
