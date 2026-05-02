/**
 * /api/auth/register — thin wire-up around the auth service.
 */

import { wrapResponse } from '../../../../shared/httpx';
import { wireService } from '../../../../shared/wire';
import { buildAuthService } from '../../../../auth/depts';
import * as authRoutes from '../../../../auth/routes';

const auth = wireService(buildAuthService);

export const POST = wrapResponse((req, ctx) => authRoutes.postRegister(auth())(req, ctx));
