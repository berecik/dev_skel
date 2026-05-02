/**
 * /api/items/[id] — thin wire-up around the items service.
 */

import { wrapResponse } from '../../../../shared/httpx';
import { getDeps, wireService } from '../../../../shared/wire';
import { buildItemsService } from '../../../../items/depts';
import * as itemRoutes from '../../../../items/routes';

const items = wireService(buildItemsService);

export const GET = wrapResponse((req, ctx) => itemRoutes.getOne(items(), getDeps())(req, ctx));
export const PATCH = wrapResponse((req, ctx) =>
  itemRoutes.patchUpdate(items(), getDeps())(req, ctx),
);
export const DELETE = wrapResponse((req, ctx) =>
  itemRoutes.deleteOne(items(), getDeps())(req, ctx),
);
