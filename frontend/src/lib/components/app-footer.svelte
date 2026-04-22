<script lang="ts">
  import ThemeToggle from "lib/components/theme-toggle.svelte";
</script>

<footer
  class="mx-auto mt-20 flex w-full max-w-screen-xl flex-col items-start justify-between gap-3 border-t border-rule px-6 pt-6 pb-6 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3 sm:flex-row sm:items-center md:px-10"
>
  <div>© {new Date().getFullYear()} · Arxiu fet per oients del programa</div>
  <div class="flex flex-wrap items-center gap-4 sm:gap-6">
    <ThemeToggle />
  </div>
</footer>
