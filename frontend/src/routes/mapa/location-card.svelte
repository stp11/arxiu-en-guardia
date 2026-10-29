<script lang="ts">
  import { type LocationWithCount, getEpisodesApiEpisodesGet } from "#client";
  import { formatDate, hasDescription } from "#lib/utils.js";
  import { ArrowRight, Loader, XIcon } from "@lucide/svelte";
  import { createInfiniteQuery } from "@tanstack/svelte-query";

  type Props = {
    location: LocationWithCount;
    onclose: () => void;
  };

  let { location, onclose }: Props = $props();

  const pageSize = 20;

  // Newest first, a page at a time.
  const query = createInfiniteQuery(() => ({
    queryKey: ["episodes", "location", location.slug],
    queryFn: async ({ pageParam }) =>
      (
        await getEpisodesApiEpisodesGet({
          query: { categories: location.slug, page: pageParam, size: pageSize },
          throwOnError: true,
        })
      ).data,
    initialPageParam: 1,
    getNextPageParam: (last) => (last.page < last.pages ? last.page + 1 : undefined),
    staleTime: 1000 * 60 * 10,
  }));

  const items = $derived(query.data?.pages.flatMap((page) => page.items) ?? []);
  // As many placeholders as the first page will have, up to three.
  const placeholders = $derived(Math.min(location.count, 3));
</script>

<aside
  aria-label={`Episodis sobre ${location.name}`}
  class="absolute inset-x-0 bottom-0 z-10 flex max-h-[55%] flex-col border-t border-rule bg-popover shadow-[0_-8px_24px_-12px_rgb(0_0_0/0.35)] md:inset-x-auto md:top-3 md:bottom-auto md:left-3 md:max-h-[calc(100%-1.5rem)] md:w-[380px] md:border"
>
  <header class="flex items-start justify-between gap-3 border-b border-rule px-4 pt-3 pb-3">
    <div>
      <p class="font-mono text-[10px] uppercase tracking-[0.12em] text-teal">Localització</p>
      <h2 class="font-serif text-[26px] leading-tight font-semibold text-ink">{location.name}</h2>
      <p class="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
        {location.count === 1 ? "1 episodi" : `${location.count} episodis`}
      </p>
    </div>
    <button
      type="button"
      onclick={onclose}
      aria-label="Tanca"
      class="-mr-1 p-1 text-ink-3 hover:text-vermillion-deep"
    >
      <XIcon class="size-4" />
    </button>
  </header>

  {#if query.isPending}
    <ol class="m-0 list-none p-0" aria-busy="true" aria-label="Carregant episodis">
      {#each Array.from({ length: placeholders }) as _, i (i)}
        <li class="animate-pulse border-b border-rule px-4 py-3 last:border-b-0">
          <span class="block h-2.5 w-20 rounded-sm bg-paper-edge/70"></span>
          <span
            class="mt-2 block h-5 rounded-sm bg-paper-edge"
            style:width="{55 + ((i * 13) % 35)}%"
          ></span>
          <span class="mt-2 block h-3 w-[92%] rounded-sm bg-paper-edge/70"></span>
          <span
            class="mt-1.5 block h-3 rounded-sm bg-paper-edge/70"
            style:width="{60 + ((i * 11) % 25)}%"
          ></span>
        </li>
      {/each}
    </ol>
  {:else if query.isError}
    <p class="px-4 py-4 text-[13px] text-ink-3">No s'han pogut carregar els episodis.</p>
  {:else}
    {#key location.slug}
      <div class="overflow-y-auto">
        <ol class="m-0 list-none p-0">
          {#each items as ep (ep.id)}
            <li
              class="group relative border-b border-rule px-4 py-3 last:border-b-0 hover:bg-vermillion/5"
            >
              {#if ep.published_at}
                <p class="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
                  {formatDate(ep.published_at, "short")}
                </p>
              {/if}
              <a
                href={`/episodis/${ep.id}/${ep.slug}`}
                class="block font-serif text-[19px] leading-tight font-semibold text-ink no-underline group-hover:text-vermillion-deep before:absolute before:inset-0 before:content-['']"
              >
                {ep.title}
              </a>
              {#if hasDescription(ep.description)}
                <p class="mt-1 line-clamp-3 text-[15px] md:text-[13px] leading-snug text-ink-2">
                  {ep.description}
                </p>
              {/if}
              <span
                class="mt-1.5 inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.1em] text-vermillion-deep"
              >
                Veure l'episodi <ArrowRight class="size-3" />
              </span>
            </li>
          {/each}
        </ol>
        {#if query.hasNextPage}
          <button
            type="button"
            onclick={() => query.fetchNextPage()}
            disabled={query.isFetchingNextPage}
            class="flex w-full items-center justify-center gap-2 border-t border-rule px-4 py-3 font-mono text-[10px] uppercase tracking-[0.1em] text-vermillion-deep hover:bg-vermillion/5 disabled:text-ink-3"
          >
            {#if query.isFetchingNextPage}
              <Loader class="size-3 animate-spin" /> Carregant…
            {:else}
              Veure més capítols
            {/if}
          </button>
          {#if query.isFetchNextPageError}
            <p class="px-4 pb-3 text-center text-[12px] text-ink-3">
              No s'han pogut carregar. Torna-ho a provar.
            </p>
          {/if}
        {/if}
      </div>
    {/key}
  {/if}
</aside>
