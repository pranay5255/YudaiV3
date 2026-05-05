import { proxyBackendRequest } from '../_lib/backend';

export default {
  fetch(request: Request): Promise<Response> {
    return proxyBackendRequest(request);
  },
};
