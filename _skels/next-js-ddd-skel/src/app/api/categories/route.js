/**
 * /api/categories — thin wire-up around the categories service.
 */

import { wrapResponse } from '../../../shared/httpx';
import { getDeps, wireService } from '../../../shared/wire';
import { buildCategoriesService } from '../../../categories/depts';
import * as categoryRoutes from '../../../categories/routes';

const categories = wireService(buildCategoriesService);

export const GET = wrapResponse((req, ctx) =>
  categoryRoutes.getList(categories(), getDeps())(req, ctx),
);
export const POST = wrapResponse((req, ctx) =>
  categoryRoutes.postCreate(categories(), getDeps())(req, ctx),
);
