import adapter from "@sveltejs/adapter-static";
import { sveltekit } from "@sveltejs/kit/vite";
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";
import tailwindcss from "@tailwindcss/vite";
import path from "path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [
    tailwindcss(),
    sveltekit({
      preprocess: vitePreprocess(),
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
    }),
  ],
  resolve: {
    alias: {
      src: path.resolve(import.meta.dirname, "src"),
      lib: path.resolve(import.meta.dirname, "src/lib"),
      client: path.resolve(import.meta.dirname, "src/client"),
    },
  },
});
