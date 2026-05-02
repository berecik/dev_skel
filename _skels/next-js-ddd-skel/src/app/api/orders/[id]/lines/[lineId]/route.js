/**
 * /api/orders/[id]/lines/[lineId] — thin wire-up around the orders service.
 */

import { wrapResponse } from '../../../../../../shared/httpx';
import { getDeps, wireService } from '../../../../../../shared/wire';
import { buildOrdersService } from '../../../../../../orders/depts';
import * as orderRoutes from '../../../../../../orders/routes';

const orders = wireService(buildOrdersService);

export const DELETE = wrapResponse((req, ctx) =>
  orderRoutes.deleteLine(orders(), getDeps())(req, ctx),
);
