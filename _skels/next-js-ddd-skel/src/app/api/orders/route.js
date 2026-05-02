/**
 * /api/orders — thin wire-up around the orders service.
 */

import { wrapResponse } from '../../../shared/httpx';
import { getDeps, wireService } from '../../../shared/wire';
import { buildOrdersService } from '../../../orders/depts';
import * as orderRoutes from '../../../orders/routes';

const orders = wireService(buildOrdersService);

export const GET = wrapResponse((req, ctx) =>
  orderRoutes.getList(orders(), getDeps())(req, ctx),
);
export const POST = wrapResponse((req, ctx) =>
  orderRoutes.postCreate(orders(), getDeps())(req, ctx),
);
