<script lang="ts">
  import { onMount } from "svelte";

  import { MoonIcon, SunIcon } from "@lucide/svelte";

  let isDark = $state(false);

  onMount(() => {
    isDark = document.documentElement.classList.contains("dark");
  });

  const toggle = () => {
    isDark = !isDark;
    document.documentElement.classList.toggle("dark", isDark);
    localStorage.setItem("theme", isDark ? "dark" : "light");
  };
</script>

<button
  onclick={toggle}
  aria-label={isDark ? "Activa el tema clar" : "Activa el tema fosc"}
  class="text-ink-2 p-1"
>
  {#if isDark}
    <SunIcon class="size-4" />
  {:else}
    <MoonIcon class="size-4" />
  {/if}
</button>
