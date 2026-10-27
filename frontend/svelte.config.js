import adapter from "@sveltejs/adapter-static";
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";

/** @type {import('@sveltejs/kit').Config} */
const config = {
  // Consult https://svelte.dev/docs/kit/integrations
  // for more information about preprocessors
  preprocess: vitePreprocess(),
  kit: {
    alias: {
      src: "./src",
      lib: "./src/lib",
      client: "./src/client",
    },
    adapter: adapter({
      fallback: "index.html",
    }),
    prerender: {
      entries: ["/sitemap.xml"],
      handleHttpError: "ignore",
      handleMissingId: "ignore",
      handleUnseenRoutes: "ignore",
    },
  },
};

export default config;
