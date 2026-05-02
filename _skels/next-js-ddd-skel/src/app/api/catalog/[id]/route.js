/**
 * /api/catalog/[id] — thin wire-up around the catalog service.
 */

import { wrapResponse } from '../../../../shared/httpx';
import { getDeps, wireService } from '../../../../shared/wire';
import { buildCatalogService } from '../../../../catalog/depts';
import * as catalogRoutes from '../../../../catalog/routes';

const catalog = wireService(buildCatalogService);

export const GET = wrapResponse((req, ctx) =>
  catalogRoutes.getOne(catalog(), getDeps())(req, ctx),
);
