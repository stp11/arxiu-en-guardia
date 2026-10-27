import { defineConfig } from "@hey-api/openapi-ts";

export default defineConfig({
  input: "http://localhost:8000/openapi.json",
  output: {
    format: "prettier",
    lint: "eslint",
    path: "src/client",
  },
  plugins: [
    {
      name: "@hey-api/client-fetch",
      runtimeConfigPath: "#client-api",
    },
  ],
});
