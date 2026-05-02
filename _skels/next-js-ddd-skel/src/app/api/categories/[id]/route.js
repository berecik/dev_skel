/**
 * /api/categories/[id] — thin wire-up around the categories service.
 */

import { wrapResponse } from '../../../../shared/httpx';
import { getDeps, wireService } from '../../../../shared/wire';
import { buildCategoriesService } from '../../../../categories/depts';
import * as categoryRoutes from '../../../../categories/routes';

const categories = wireService(buildCategoriesService);

export const GET = wrapResponse((req, ctx) =>
  categoryRoutes.getOne(categories(), getDeps())(req, ctx),
);
export const PUT = wrapResponse((req, ctx) =>
  categoryRoutes.putUpdate(categories(), getDeps())(req, ctx),
);
export const DELETE = wrapResponse((req, ctx) =>
  categoryRoutes.deleteOne(categories(), getDeps())(req, ctx),
);
