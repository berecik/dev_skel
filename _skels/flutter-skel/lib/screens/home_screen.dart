/// `HomeScreen` — composes the dev_skel Flutter example.
///
/// Mirror of React's authenticated branch in `src/App.tsx`. Renders a
/// header with the wrapper-shared backend URL + JWT issuer (proves
/// the env loader wired correctly), an [ItemForm] for creating new
/// items (with an optional category selector), and an [ItemListView]
/// showing the items with the persistent `showCompleted` filter from
/// the wrapper-shared state layer.

import 'package:flutter/material.dart';

import '../auth/auth_scope.dart';
import '../config.dart';
import '../controllers/categories_controller.dart';
import '../controllers/items_controller.dart';
import 'item_form.dart';
import 'item_list.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({
    super.key,
    required this.config,
    required this.itemsController,
    this.categoriesController,
  });

  final AppConfig config;
  final ItemsController itemsController;
  final CategoriesController? categoriesController;

  @override
  Widget build(BuildContext context) {
    final tokenStore = AuthScope.read(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('dev_skel Flutter'),
        actions: <Widget>[
          IconButton(
            tooltip: 'Sign out',
            onPressed: tokenStore.clear,
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              _Header(config: config),
              const SizedBox(height: 12),
              ItemForm(
                controller: itemsController,
                categoriesController: categoriesController,
              ),
              const SizedBox(height: 12),
              ItemListView(controller: itemsController),
            ],
          ),
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.config});

  final AppConfig config;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Wrapper-shared API · Flutter ${theme.platform.name}',
              style: theme.textTheme.titleSmall,
            ),
            const SizedBox(height: 8),
            _kv(context, 'Backend URL', config.backendUrl),
            _kv(context, 'JWT issuer', config.jwt.issuer),
            _kv(
              context,
              'Sibling services',
              config.services.length.toString(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _kv(BuildContext context, String key, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Text.rich(
        TextSpan(
          children: <InlineSpan>[
            TextSpan(
              text: '$key: ',
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            TextSpan(text: value),
          ],
        ),
      ),
    );
  }
}
