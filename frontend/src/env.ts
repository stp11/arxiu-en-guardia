import { defineEnvVars } from "@sveltejs/kit/env";

export const variables = defineEnvVars({
  VITE_API_URL: {
    public: true,
    static: true,
    description: "Base URL of the Arxiu En Guàrdia API, without a trailing slash",
    schema: (value) => {
      if (!value) throw new Error("VITE_API_URL must be set");
      try {
        new URL(value);
      } catch {
        throw new Error(`VITE_API_URL is not a valid URL: ${value}`);
      }
      return value;
    },
  },
});
