import type { Config } from "./client/client/index.js";

export const createClientConfig = (config?: Config): Config => ({
  ...config,
  baseUrl: import.meta.env.VITE_API_URL,
});
