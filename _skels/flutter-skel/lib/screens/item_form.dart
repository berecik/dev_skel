/// `ItemForm` — controlled form that creates a new item via the
/// shared [ItemsController].
///
/// Mirrors React's `ItemForm.tsx`. Receives the controller from the
/// parent so multiple widgets can share a single cache. Optionally
/// accepts a [CategoriesController] to show a category dropdown; when
/// omitted the form works exactly as before (no category field).

import 'package:flutter/material.dart';

import '../api/categories_client.dart';
import '../api/items_client.dart';
import '../controllers/categories_controller.dart';
import '../controllers/items_controller.dart';

class ItemForm extends StatefulWidget {
  const ItemForm({
    super.key,
    required this.controller,
    this.categoriesController,
  });

  final ItemsController controller;
  final CategoriesController? categoriesController;

  @override
  State<ItemForm> createState() => _ItemFormState();
}

class _ItemFormState extends State<ItemForm> {
  final TextEditingController _name = TextEditingController();
  final TextEditingController _description = TextEditingController();
  int? _selectedCategoryId;
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    _description.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_name.text.trim().isEmpty) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.controller.create(
        NewItem(
          name: _name.text.trim(),
          description:
              _description.text.isEmpty ? null : _description.text,
          categoryId: _selectedCategoryId,
        ),
      );
      _name.clear();
      _description.clear();
      setState(() => _selectedCategoryId = null);
    } on AuthError {
      setState(() => _error = 'Your session expired — please sign in again.');
    } catch (err) {
      setState(() => _error = err.toString());
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Text(
              'New item',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _name,
              decoration: const InputDecoration(labelText: 'Name'),
              textInputAction: TextInputAction.next,
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _description,
              maxLines: 2,
              decoration: const InputDecoration(labelText: 'Description'),
              textInputAction: TextInputAction.next,
            ),
            if (widget.categoriesController != null) ...<Widget>[
              const SizedBox(height: 8),
              _CategoryDropdown(
                categoriesController: widget.categoriesController!,
                selectedId: _selectedCategoryId,
                onChanged: (id) => setState(() => _selectedCategoryId = id),
              ),
            ],
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton(
                onPressed: _submitting ? null : _submit,
                child: Text(_submitting ? 'Saving…' : 'Create item'),
              ),
            ),
            if (_error != null) ...<Widget>[
              const SizedBox(height: 8),
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Category picker dropdown that listens to the [CategoriesController]
/// and rebuilds whenever the categories list changes.
class _CategoryDropdown extends StatelessWidget {
  const _CategoryDropdown({
    required this.categoriesController,
    required this.selectedId,
    required this.onChanged,
  });

  final CategoriesController categoriesController;
  final int? selectedId;
  final ValueChanged<int?> onChanged;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: categoriesController,
      builder: (context, _) {
        final categories = categoriesController.categories;
        if (categoriesController.loading && categories.isEmpty) {
          return const SizedBox.shrink();
        }
        return DropdownButtonFormField<int?>(
          value: selectedId,
          decoration: const InputDecoration(labelText: 'Category'),
          items: <DropdownMenuItem<int?>>[
            const DropdownMenuItem<int?>(
              value: null,
              child: Text('None'),
            ),
            for (final ItemCategory cat in categories)
              DropdownMenuItem<int?>(
                value: cat.id,
                child: Text(cat.name),
              ),
          ],
          onChanged: onChanged,
        );
      },
    );
  }
}
