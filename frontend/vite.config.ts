import { sveltekit } from "@sveltejs/kit/vite";
import tailwindcss from "@tailwindcss/vite";
import path from "path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  resolve: {
    alias: {
      src: path.resolve(__dirname, "src"),
      lib: path.resolve(__dirname, "src/lib"),
      client: path.resolve(__dirname, "src/client"),
    },
  },
});
