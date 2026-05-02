/**
 * /api/orders/[id] — thin wire-up around the orders service.
 */

import { wrapResponse } from '../../../../shared/httpx';
import { getDeps, wireService } from '../../../../shared/wire';
import { buildOrdersService } from '../../../../orders/depts';
import * as orderRoutes from '../../../../orders/routes';

const orders = wireService(buildOrdersService);

export const GET = wrapResponse((req, ctx) =>
  orderRoutes.getOne(orders(), getDeps())(req, ctx),
);
