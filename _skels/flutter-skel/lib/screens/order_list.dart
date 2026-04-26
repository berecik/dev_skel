/// `OrderListView` — renders the orders returned by [OrdersController]
/// with status badges and tap-to-detail navigation.
///
/// Mirrors the `ItemListView` pattern: a `ListenableBuilder` around
/// the controller so the list rebuilds on every `notifyListeners()`,
/// a heading with the count, and `shrinkWrap: true` +
/// `NeverScrollableScrollPhysics` so the inner list sizes itself to
/// its children and delegates scrolling to the outer
/// `SingleChildScrollView` in `HomeScreen`.

import 'package:flutter/material.dart';

import '../api/orders_client.dart';
import '../controllers/orders_controller.dart';

class OrderListView extends StatelessWidget {
  const OrderListView({super.key, required this.controller});

  final OrdersController controller;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final orders = controller.orders;

        if (controller.loading && orders.isEmpty) {
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
                      'Orders (${orders.length})',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                  IconButton(
                    tooltip: 'Refresh',
                    icon: const Icon(Icons.refresh),
                    onPressed:
                        controller.loading ? null : controller.refresh,
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
            if (orders.isEmpty)
              Padding(
                padding: const EdgeInsets.all(24),
                child: Text(
                  'No orders yet.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              )
            else
              ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: orders.length,
                separatorBuilder: (_, __) => const Divider(height: 1),
                itemBuilder: (context, index) {
                  final order = orders[index];
                  return ListTile(
                    title: Text('Order #${order.id}'),
                    subtitle: Text(
                      'Status: ${order.status}  |  Created: ${order.createdAt}',
                    ),
                    trailing: _StatusChip(status: order.status),
                    onTap: () => _showOrderDetail(context, order),
                  );
                },
              ),
          ],
        );
      },
    );
  }

  void _showOrderDetail(BuildContext context, Order order) {
    showDialog<void>(
      context: context,
      builder: (context) => _OrderDetailDialog(
        controller: controller,
        orderId: order.id,
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final Color color;
    switch (status.toLowerCase()) {
      case 'draft':
        color = Colors.grey;
      case 'submitted':
        color = Colors.blue;
      case 'approved':
        color = Colors.green;
      case 'rejected':
        color = Colors.red;
      default:
        color = Colors.orange;
    }
    return Chip(
      label: Text(status),
      backgroundColor: color.withValues(alpha: 0.15),
      labelStyle: TextStyle(color: color),
    );
  }
}

class _OrderDetailDialog extends StatefulWidget {
  const _OrderDetailDialog({
    required this.controller,
    required this.orderId,
  });

  final OrdersController controller;
  final int orderId;

  @override
  State<_OrderDetailDialog> createState() => _OrderDetailDialogState();
}

class _OrderDetailDialogState extends State<_OrderDetailDialog> {
  OrderDetail? _detail;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadDetail();
  }

  Future<void> _loadDetail() async {
    try {
      final detail = await widget.controller.getDetail(widget.orderId);
      if (mounted) {
        setState(() {
          _detail = detail;
          _loading = false;
        });
      }
    } catch (err) {
      if (mounted) {
        setState(() {
          _error = err.toString();
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('Order #${widget.orderId}'),
      content: SizedBox(
        width: double.maxFinite,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? Text('Error: $_error')
                : _buildDetailContent(),
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Close'),
        ),
      ],
    );
  }

  Widget _buildDetailContent() {
    final detail = _detail;
    if (detail == null) return const Text('No data');

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Text('Status: ${detail.status}'),
          Text('Created: ${detail.createdAt}'),
          if (detail.submittedAt != null)
            Text('Submitted: ${detail.submittedAt}'),
          if (detail.waitMinutes != null)
            Text('Wait: ${detail.waitMinutes} min'),
          if (detail.feedback != null) Text('Feedback: ${detail.feedback}'),
          const SizedBox(height: 12),
          Text(
            'Lines (${detail.lines.length})',
            style: Theme.of(context).textTheme.titleSmall,
          ),
          if (detail.lines.isEmpty)
            const Text('No lines.')
          else
            for (final line in detail.lines)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Text(
                  'Catalog #${line.catalogItemId}  x${line.quantity}  @ \$${line.unitPrice.toStringAsFixed(2)}',
                ),
              ),
          if (detail.address != null) ...<Widget>[
            const SizedBox(height: 12),
            Text(
              'Address',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            Text('${detail.address!.street}, ${detail.address!.city}'),
            Text('ZIP: ${detail.address!.zipCode}'),
            if (detail.address!.phone.isNotEmpty)
              Text('Phone: ${detail.address!.phone}'),
            if (detail.address!.notes.isNotEmpty)
              Text('Notes: ${detail.address!.notes}'),
          ],
        ],
      ),
    );
  }
}
