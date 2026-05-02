/**
 * /api/catalog — thin wire-up around the catalog service.
 */

import { wrapResponse } from '../../../shared/httpx';
import { getDeps, wireService } from '../../../shared/wire';
import { buildCatalogService } from '../../../catalog/depts';
import * as catalogRoutes from '../../../catalog/routes';

const catalog = wireService(buildCatalogService);

export const GET = wrapResponse((req, ctx) => catalogRoutes.getList(catalog())(req, ctx));
export const POST = wrapResponse((req, ctx) =>
  catalogRoutes.postCreate(catalog(), getDeps())(req, ctx),
);
