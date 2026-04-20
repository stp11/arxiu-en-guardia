<script lang="ts">
  import { page } from "$app/state";
  import { ArrowLeft } from "@lucide/svelte";
</script>

<div class="mx-auto flex w-full max-w-[1100px] flex-1 flex-col px-6 pt-8 pb-12 md:px-10 md:pt-14">
  <!-- Mini masthead bar -->
  <div
    class="flex items-center justify-between gap-4 border-b-[3px] border-double border-rule pt-5 pb-4"
  >
    <a
      href="/"
      class="inline-block font-serif leading-[0.95] tracking-[-0.005em] text-ink"
      aria-label="Arxiu En Guàrdia"
    >
      <span class="block text-[15px] font-medium md:text-base">Arxiu</span>
      <span class="block text-xl font-medium italic text-vermillion-deep md:text-2xl">
        En&nbsp;Guàrdia
      </span>
    </a>
    <a
      href="/"
      class="inline-flex items-center gap-2 rounded-sm border border-ink bg-ink px-3 py-2 font-mono text-[11px] uppercase tracking-[0.1em] text-paper transition-colors hover:border-vermillion-deep hover:bg-vermillion-deep"
    >
      <ArrowLeft class="size-3.5" />
      {page.status === 404 ? "Torna al present" : "Torna a l'arxiu"}
    </a>
  </div>

  <div class="flex flex-1 items-center justify-center py-16">
    <div class="mx-auto max-w-md space-y-5 text-center">
      <p class="font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-vermillion-deep">
        Error {page.status}
      </p>
      <h1
        class="font-serif text-[clamp(2rem,5vw,3.25rem)] font-medium text-balance leading-[1.05] tracking-[-0.015em] text-ink"
      >
        {#if page.status === 404}
          T'has perdut en un moment indeterminat de la història.
        {:else}
          Alguna cosa ha anat malament.
        {/if}
      </h1>
      <p class="font-serif text-[17px] italic leading-snug text-ink-2">
        {#if page.status === 404}
          La pàgina que busques no es troba a l'arxiu.
        {:else}
          Torna-ho a provar d'aquí a una estona.
        {/if}
      </p>
    </div>
  </div>
</div>
