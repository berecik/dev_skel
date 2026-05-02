/**
 * /api/items/[id]/complete — thin wire-up around the items service.
 */

import { wrapResponse } from '../../../../../shared/httpx';
import { getDeps, wireService } from '../../../../../shared/wire';
import { buildItemsService } from '../../../../../items/depts';
import * as itemRoutes from '../../../../../items/routes';

const items = wireService(buildItemsService);

export const POST = wrapResponse((req, ctx) =>
  itemRoutes.postComplete(items(), getDeps())(req, ctx),
);
