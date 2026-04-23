<script lang="ts">
  import ThemeToggle from "lib/components/theme-toggle.svelte";
</script>

<footer
  class="mx-auto mt-20 flex w-full max-w-screen-xl justify-between gap-2 border-t border-rule px-4 py-4 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3 flex-row items-center md:py-6 md:px-10"
>
  <div>© {new Date().getFullYear()} · Arxiu fet per oients del programa</div>
  <div class="flex flex-wrap items-center gap-4 sm:gap-6">
    <ThemeToggle />
  </div>
</footer>
