/**
 * /api/orders/[id]/address — thin wire-up around the orders service.
 */

import { wrapResponse } from '../../../../../shared/httpx';
import { getDeps, wireService } from '../../../../../shared/wire';
import { buildOrdersService } from '../../../../../orders/depts';
import * as orderRoutes from '../../../../../orders/routes';

const orders = wireService(buildOrdersService);

export const PUT = wrapResponse((req, ctx) =>
  orderRoutes.putAddress(orders(), getDeps())(req, ctx),
);
