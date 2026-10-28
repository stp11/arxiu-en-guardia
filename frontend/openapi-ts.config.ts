import { defineConfig } from "@hey-api/openapi-ts";

export default defineConfig({
  input: "http://localhost:8000/openapi.json",
  output: {
    path: "src/client",
  },
  plugins: [
    {
      name: "@hey-api/client-fetch",
      runtimeConfigPath: "#client-api",
    },
  ],
});
