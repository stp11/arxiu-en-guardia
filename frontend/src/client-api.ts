import { VITE_API_URL } from "$app/env/public";

import type { Config } from "./client/client/index.js";

export const createClientConfig = (config?: Config): Config => ({
  ...config,
  baseUrl: VITE_API_URL,
});
