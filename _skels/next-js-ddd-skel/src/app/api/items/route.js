/**
 * /api/items — thin wire-up around the items service.
 */

import { wrapResponse } from '../../../shared/httpx';
import { getDeps, wireService } from '../../../shared/wire';
import { buildItemsService } from '../../../items/depts';
import * as itemRoutes from '../../../items/routes';

const items = wireService(buildItemsService);

export const GET = wrapResponse((req, ctx) => itemRoutes.getList(items(), getDeps())(req, ctx));
export const POST = wrapResponse((req, ctx) =>
  itemRoutes.postCreate(items(), getDeps())(req, ctx),
);
