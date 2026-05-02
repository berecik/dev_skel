/**
 * OrdersService — aggregate root for the order lifecycle.
 *
 * The pre-DDD routes carried a lot of inline logic; this service
 * exposes a clean high-level surface (draft / addLine / removeLine /
 * setAddress / submit / approve / reject) and keeps every error-mode
 * mapping in one place.
 */

const { DomainError } = require('../shared/errors');
const { assertOrderRepository } = require('./repository');

class OrdersService {
  constructor(repo) {
    assertOrderRepository(repo);
    this.repo = repo;
  }

  list(userId) {
    return this.repo.listForUser(userId);
  }

  /** Header + lines + address. Throws NotFound if missing or not owned. */
  get(userId, orderId) {
    const detail = this.repo.getDetailForUser(userId, orderId);
    if (!detail) throw DomainError.notFound('Order not found');
    return detail;
  }

  draft(userId) {
    return this.repo.createDraft(userId);
  }

  addLine(userId, orderId, { catalog_item_id, quantity }) {
    const order = this.repo.getForUser(userId, orderId);
    if (!order) throw DomainError.notFound('Order not found');
    if (order.status !== 'draft') {
      throw DomainError.validation('Can only add lines to draft orders');
    }
    if (!catalog_item_id) {
      throw DomainError.validation('catalog_item_id is required');
    }
    const catalogItem = this.repo.getCatalogItem(catalog_item_id);
    if (!catalogItem) throw DomainError.notFound('Catalog item not found');

    return this.repo.addLine(orderId, {
      catalog_item_id,
      quantity: quantity || 1,
      unit_price: catalogItem.price || 0.0,
    });
  }

  removeLine(userId, orderId, lineId) {
    const order = this.repo.getForUser(userId, orderId);
    if (!order) throw DomainError.notFound('Order not found');
    if (order.status !== 'draft') {
      throw DomainError.validation('Can only remove lines from draft orders');
    }
    const line = this.repo.getLine(orderId, lineId);
    if (!line) throw DomainError.notFound('Order line not found');
    this.repo.removeLine(orderId, lineId);
  }

  setAddress(userId, orderId, addr) {
    const order = this.repo.getForUser(userId, orderId);
    if (!order) throw DomainError.notFound('Order not found');
    if (order.status !== 'draft') {
      throw DomainError.validation('Order must be in draft status');
    }
    if (!addr || !addr.street || !addr.city || !addr.zip_code) {
      throw DomainError.validation('street, city, and zip_code are required');
    }
    this.repo.setAddress(orderId, addr);
    return { ok: true };
  }

  submit(userId, orderId) {
    const order = this.repo.getForUser(userId, orderId);
    if (!order) throw DomainError.notFound('Order not found');
    if (order.status !== 'draft') {
      throw DomainError.validation('Only draft orders can be submitted');
    }
    return this.repo.updateStatus(orderId, 'pending');
  }

  /**
   * `approve` is a privileged transition — the pre-DDD routes did not
   * check user-ownership before approving, so we don't either. The
   * route layer still requires authentication.
   */
  approve(orderId, { wait_minutes, feedback } = {}) {
    const raw = this.repo.getRaw(orderId);
    if (!raw) throw DomainError.notFound('Order not found');
    if (raw.status !== 'pending') {
      throw DomainError.validation('Only pending orders can be approved');
    }
    return this.repo.updateStatus(orderId, 'approved', {
      wait_minutes: wait_minutes ?? null,
      feedback: feedback || null,
    });
  }

  reject(orderId, { feedback } = {}) {
    const raw = this.repo.getRaw(orderId);
    if (!raw) throw DomainError.notFound('Order not found');
    if (raw.status !== 'pending') {
      throw DomainError.validation('Only pending orders can be rejected');
    }
    return this.repo.updateStatus(orderId, 'rejected', {
      feedback: feedback || null,
    });
  }
}

module.exports = { OrdersService };
