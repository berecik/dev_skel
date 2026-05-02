/**
 * /api/state/[key] — thin wire-up around the state service.
 *   PUT    upsert a single slice
 *   DELETE remove a single slice
 */

import { wrapResponse } from '../../../../shared/httpx';
import { getDeps, wireService } from '../../../../shared/wire';
import { buildStateService } from '../../../../state/depts';
import * as stateRoutes from '../../../../state/routes';

const state = wireService(buildStateService);

export const PUT = wrapResponse((req, ctx) =>
  stateRoutes.putUpsert(state(), getDeps())(req, ctx),
);
export const DELETE = wrapResponse((req, ctx) =>
  stateRoutes.deleteOne(state(), getDeps())(req, ctx),
);
