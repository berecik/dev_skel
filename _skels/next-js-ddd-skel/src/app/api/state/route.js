/**
 * /api/state — thin wire-up around the state service.
 *
 * Wire format: { "key1": "value1", ... } where every value is a JSON
 * string the client decodes locally.
 */

import { wrapResponse } from '../../../shared/httpx';
import { getDeps, wireService } from '../../../shared/wire';
import { buildStateService } from '../../../state/depts';
import * as stateRoutes from '../../../state/routes';

const state = wireService(buildStateService);

export const GET = wrapResponse((req, ctx) =>
  stateRoutes.getList(state(), getDeps())(req, ctx),
);
