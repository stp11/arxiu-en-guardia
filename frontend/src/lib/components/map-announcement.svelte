<script lang="ts">
  import { onMount } from "svelte";
  import { slide } from "svelte/transition";

  import { page } from "$app/state";
  import { XIcon } from "@lucide/svelte";

  const KEY = "map-announcement";
  const UNTIL = Date.parse("2026-12-01");

  // Without storage it couldn't stay closed, so it isn't shown at all.
  const closed = () => {
    try {
      return localStorage.getItem(KEY) !== null;
    } catch {
      return true;
    }
  };

  // Decided in the browser: on pages rendered on the server, there's no storage to read.
  let open = $state(false);
  onMount(() => {
    open = Date.now() < UNTIL && !closed();
  });
  const onMap = $derived(page.url.pathname.startsWith("/mapa"));

  const close = () => {
    open = false;
    try {
      localStorage.setItem(KEY, "closed");
    } catch {
      // Closed for this visit only.
    }
  };

  // Reaching the map, by the banner or the menu, counts as having seen it.
  $effect(() => {
    if (onMap && open) close();
  });
</script>

{#if open && !onMap}
  <aside aria-label="Novetat" out:slide={{ duration: 200 }} class="border-b border-rule bg-paper-2">
    <!-- Side padding keeps the centred text clear of the close button -->
    <div
      class="relative mx-auto flex w-full max-w-screen-xl justify-center px-12 py-2 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-2"
    >
      <a href="/mapa" class="inline-flex items-center gap-2 hover:text-ink">
        <!-- The episode list's category badge, inverted -->
        <span
          class="rounded-sm border border-vermillion-deep bg-vermillion-deep px-2 py-0.5 font-mono text-[10px] leading-snug uppercase tracking-[0.05em] whitespace-nowrap text-paper"
        >
          Novetat
        </span>
        Els episodis, ara en un mapa
      </a>
      <!-- Lined up with the theme toggle below -->
      <button
        type="button"
        onclick={close}
        aria-label="Tanca l'avís"
        class="absolute top-1/2 right-6 -translate-y-1/2 p-1 text-ink-3 hover:text-vermillion-deep md:right-10"
      >
        <XIcon class="size-3.5" />
      </button>
    </div>
  </aside>
{/if}
