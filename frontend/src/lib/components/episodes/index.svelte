<script lang="ts">
  import { untrack } from "svelte";
  import { SvelteSet, SvelteURLSearchParams } from "svelte/reactivity";

  import {
    type CategoryBase,
    type CategoryType,
    type CategoryWithCount,
    getCategoriesApiCategoriesGet,
    getCategoryCountsApiCategoriesCountsGet,
    getEpisodesApiEpisodesGet,
  } from "#client";
  import AppHero from "#lib/components/app-hero.svelte";
  import * as Sheet from "#lib/components/ui/sheet/index.js";
  import { SITE_NAME, SITE_URL } from "#lib/constants.js";
  import {
    cn,
    extractSnippet,
    hasDescription,
    highlightMatches,
    isPlainClick,
  } from "#lib/utils.js";
  import { browser } from "$app/env";
  import { goto } from "$app/navigation";
  import { page as pageStore } from "$app/state";
  import {
    ChevronLeft,
    ChevronRight,
    Loader,
    MapIcon,
    Search,
    SlidersHorizontal,
  } from "@lucide/svelte";
  import { createInfiniteQuery, createQuery, keepPreviousData } from "@tanstack/svelte-query";

  import CategoryChip from "./category-chip.svelte";
  import Facet from "./facet.svelte";

  const initialPage = 1;
  const pageSize = 25;
  const minSearchChars = 3;

  const ALL_TYPES: CategoryType[] = ["topic", "location", "character", "time_period"];
  const MONTHS_CA = [
    "gen",
    "feb",
    "març",
    "abr",
    "maig",
    "juny",
    "jul",
    "ago",
    "set",
    "oct",
    "nov",
    "des",
  ];

  // Read before the episodes query is created: setting the state on mount
  // fetched the unfiltered episodes first, then the filtered ones.
  const readUrlState = () => {
    const params = pageStore.url.searchParams;
    const state = {
      search: "",
      page: initialPage,
      order: "desc" as "asc" | "desc",
      categories: {
        topic: [],
        character: [],
        location: [],
        time_period: [],
      } as Record<CategoryType, string[]>,
      matchAll: [] as CategoryType[],
    };

    const urlPage = params.get("page");
    if (urlPage) {
      const n = Number.parseInt(urlPage, 10);
      if (!Number.isNaN(n) && n > 0) state.page = n;
    }

    const urlSearch = params.get("search");
    if (urlSearch && urlSearch.trim().length >= minSearchChars) {
      state.search = urlSearch;
    }

    const urlOrder = params.get("order");
    if (urlOrder === "asc" || urlOrder === "desc") {
      state.order = urlOrder;
    }

    for (const t of ALL_TYPES) {
      const raw = params.get(t);
      if (!raw) continue;
      // Unique, or the keyed list of selected categories throws.
      const slugs = [
        ...new Set(
          raw
            .split(",")
            .map((s) => s.trim())
            .filter((s) => s.length > 0)
        ),
      ];
      if (slugs.length > 0) state.categories[t] = slugs;
    }

    const urlMatchAll = params.get("match_all")?.split(",") ?? [];
    state.matchAll = ALL_TYPES.filter((t) => urlMatchAll.includes(t));

    return state;
  };

  const fromUrl = readUrlState();

  let searchText = $state(fromUrl.search);
  let searchQuery = $state(fromUrl.search.trim());
  let page = $state(fromUrl.page);
  let categories = $state<Record<CategoryType, string[]>>(fromUrl.categories);
  // The facets where an episode needs every selected category, not any.
  let matchAll = $state<CategoryType[]>(fromUrl.matchAll);
  let order = $state<"asc" | "desc">(fromUrl.order);
  let searchInput: HTMLInputElement | null = $state(null);
  let filtersOpen = $state(false);
  // Rows whose categories were expanded past the first few, on narrow screens.
  const expandedRows = new SvelteSet<number>();

  let urlTimer: ReturnType<typeof setTimeout> | null = null;
  const updateUrl = () => {
    if (urlTimer) clearTimeout(urlTimer);
    urlTimer = setTimeout(() => {
      const params = new SvelteURLSearchParams(pageStore.url.search);

      if (searchQuery) params.set("search", searchQuery);
      else params.delete("search");

      if (order !== "desc") params.set("order", order);
      else params.delete("order");

      if (page !== initialPage) params.set("page", String(page));
      else params.delete("page");

      for (const t of ALL_TYPES) {
        if (categories[t].length > 0) params.set(t, categories[t].join(","));
        else params.delete(t);
      }

      if (matchAllString) params.set("match_all", matchAllString);
      else params.delete("match_all");

      const qs = params.toString();
      goto(qs ? `?${qs}` : pageStore.url.pathname, {
        replace: true,
        reset: false,
      });
    }, 100);
  };

  $effect(() => {
    page; // eslint-disable-line @typescript-eslint/no-unused-expressions
    searchQuery; // eslint-disable-line @typescript-eslint/no-unused-expressions
    order; // eslint-disable-line @typescript-eslint/no-unused-expressions
    categoriesString; // eslint-disable-line @typescript-eslint/no-unused-expressions
    matchAllString; // eslint-disable-line @typescript-eslint/no-unused-expressions
    updateUrl();
  });

  let searchTimer: ReturnType<typeof setTimeout> | null = null;
  const handleSearchInput = (value: string) => {
    searchText = value;
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      const trimmed = value.trim();
      const next = trimmed.length >= minSearchChars ? trimmed : "";
      if (next !== searchQuery) {
        searchQuery = next;
        page = 1;
      }
    }, 300);
  };

  const toggleCategory = (type: CategoryType, slug: string) => {
    const current = categories[type];
    const exists = current.includes(slug);
    categories = {
      ...categories,
      [type]: exists ? current.filter((c) => c !== slug) : [...current, slug],
    };
    page = 1;
  };

  const setMatchAll = (type: CategoryType, all: boolean) => {
    if (all === matchAll.includes(type)) return;
    matchAll = all ? [...matchAll, type] : matchAll.filter((t) => t !== type);
    page = 1;
  };

  const clearAll = () => {
    categories = { topic: [], character: [], location: [], time_period: [] };
    matchAll = [];
    searchText = "";
    searchQuery = "";
    if (searchInput) searchInput.value = "";
    page = 1;
  };

  const categoriesString = $derived(Object.values(categories).flat().join(","));
  // In the order of ALL_TYPES, so the same choice is the same cache key.
  const matchAllString = $derived(ALL_TYPES.filter((t) => matchAll.includes(t)).join(","));
  // What the requests need of it: the list changes only where 2 or more
  // are selected, the counts where any is. Otherwise switching would
  // refetch the same results.
  const matchAllFor = (min: number) =>
    ALL_TYPES.filter((t) => matchAll.includes(t) && categories[t].length >= min).join(",");
  const listMatchAll = $derived(matchAllFor(2));
  const countsMatchAll = $derived(matchAllFor(1));

  const queryData = createQuery(() => ({
    queryKey: ["episodes", searchQuery, page, pageSize, order, categoriesString, listMatchAll],
    queryFn: () =>
      getEpisodesApiEpisodesGet({
        query: {
          search: searchQuery,
          page,
          size: pageSize,
          order,
          categories: categoriesString,
          match_all: listMatchAll,
        },
      }),
    placeholderData: keepPreviousData,
    staleTime: 1000 * 30,
  }));

  const items = $derived(queryData.data?.data?.items ?? []);
  const total = $derived(queryData.data?.data?.total ?? 0);
  const totalPages = $derived(queryData.data?.data?.pages ?? 0);

  const processedItems = $derived(
    items.map((ep) => {
      const desc = ep.description ?? "";
      const descShown = hasDescription(desc);
      const snippet = descShown ? extractSnippet(desc, searchQuery) : "";
      return {
        ep,
        titleChunks: highlightMatches(ep.title, searchQuery),
        descChunks: descShown ? highlightMatches(snippet, searchQuery) : [],
        descShown,
      };
    })
  );

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const getNextPageParam = (lastPage: any) => {
    const data = lastPage?.data;
    if (data?.page && data?.pages && data.page < data.pages) return data.page + 1;
    return undefined;
  };

  const makeCategoriesQuery = (type: CategoryType, size: number) =>
    createInfiniteQuery(() => ({
      queryKey: [`categories:${type}`],
      queryFn: ({ pageParam }) =>
        getCategoriesApiCategoriesGet({ query: { type, page: pageParam, size } }),
      getNextPageParam,
      initialPageParam: 1,
      staleTime: 1000 * 60 * 10,
    }));

  const topicsQuery = makeCategoriesQuery("topic", 1000);
  const locationsQuery = makeCategoriesQuery("location", 500);
  const charactersQuery = makeCategoriesQuery("character", 500);
  const timePeriodsQuery = makeCategoriesQuery("time_period", 500);

  $effect(() => {
    if (topicsQuery.data && topicsQuery.hasNextPage && !topicsQuery.isFetchingNextPage)
      untrack(() => topicsQuery.fetchNextPage());
  });
  $effect(() => {
    if (locationsQuery.data && locationsQuery.hasNextPage && !locationsQuery.isFetchingNextPage)
      untrack(() => locationsQuery.fetchNextPage());
  });
  $effect(() => {
    if (charactersQuery.data && charactersQuery.hasNextPage && !charactersQuery.isFetchingNextPage)
      untrack(() => charactersQuery.fetchNextPage());
  });
  $effect(() => {
    if (
      timePeriodsQuery.data &&
      timePeriodsQuery.hasNextPage &&
      !timePeriodsQuery.isFetchingNextPage
    )
      untrack(() => timePeriodsQuery.fetchNextPage());
  });

  const mapItems = (cats: CategoryWithCount[]) =>
    cats
      .filter((c) => !!c.slug)
      .map((c) => ({ slug: c.slug, name: c.name, count: c.count ?? 0 }))
      .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "ca"));

  const topicItems = $derived(
    mapItems(topicsQuery.data?.pages.flatMap((p) => p?.data?.items ?? []) ?? [])
  );
  const locationItems = $derived(
    mapItems(locationsQuery.data?.pages.flatMap((p) => p?.data?.items ?? []) ?? [])
  );
  const characterItems = $derived(
    mapItems(charactersQuery.data?.pages.flatMap((p) => p?.data?.items ?? []) ?? [])
  );
  const timePeriodItems = $derived(
    mapItems(timePeriodsQuery.data?.pages.flatMap((p) => p?.data?.items ?? []) ?? [])
  );

  const allCategoryItems = $derived({
    topic: topicItems,
    location: locationItems,
    character: characterItems,
    time_period: timePeriodItems,
  });

  const findItem = (type: CategoryType, slug: string) =>
    allCategoryItems[type].find((i) => i.slug === slug);

  const hasFilters = $derived(ALL_TYPES.some((t) => categories[t].length > 0));

  // The facets' counts under the current filters. Without any, the
  // categories' own counts are the same, so there's nothing to fetch; while
  // the next ones load, the last stay up rather than jumping back to those.
  const countsQuery = createQuery(() => ({
    queryKey: ["category-counts", searchQuery, categoriesString, countsMatchAll],
    queryFn: async () =>
      (
        await getCategoryCountsApiCategoriesCountsGet({
          query: { search: searchQuery, categories: categoriesString, match_all: countsMatchAll },
          throwOnError: true,
        })
      ).data,
    // By slug, for the facets to look up.
    select: (counts) => new Map(counts.map((c) => [c.slug, c.count])),
    enabled: browser && hasFilters,
    placeholderData: keepPreviousData,
    staleTime: 1000 * 30,
  }));
  const facetCounts = $derived(hasFilters ? countsQuery.data : undefined);
  // Those with a chip: unknown slugs are ignored by the list, so not counted.
  const activeFilterCount = $derived(
    ALL_TYPES.reduce((acc, t) => acc + categories[t].filter((slug) => findItem(t, slug)).length, 0)
  );

  const isSelected = (c: CategoryBase) =>
    categories[c.type as CategoryType]?.includes(c.slug) ?? false;
  // The ticked ones first, so they're among the few shown on narrow screens.
  const tickedFirst = (cats: CategoryBase[]) => [
    ...cats.filter(isSelected),
    ...cats.filter((c) => !isSelected(c)),
  ];

  const fmtDate = (iso: string) => {
    const d = new Date(iso);

    return {
      day: String(d.getDate()).padStart(2, "0"),
      my: `${MONTHS_CA[d.getMonth()]} ${d.getFullYear()}`,
    };
  };

  const pageNumbers = $derived.by(() => {
    const out: (number | "…")[] = [];
    const last = totalPages;
    const p = page;
    if (last <= 7) {
      for (let i = 1; i <= last; i++) out.push(i);
    } else {
      out.push(1);
      if (p > 3) out.push("…");
      for (let i = Math.max(2, p - 1); i <= Math.min(last - 1, p + 1); i++) out.push(i);
      if (p < last - 2) out.push("…");
      out.push(last);
    }
    return out;
  });

  // The page links' href: the current URL with only ?page= changed. It's for
  // what the browser does with a link (a new tab, copying it, crawlers).
  const pageHref = (n: number) => {
    const params = new SvelteURLSearchParams(pageStore.url.search);
    if (n === initialPage) params.delete("page");
    else params.set("page", String(n));
    const qs = params.toString();
    return qs ? `?${qs}` : pageStore.url.pathname;
  };

  // A plain click sets the page here instead of following the href: this
  // component reads the URL only when it's created, so a navigation to
  // ?page=3 on the same route would change the URL but not the list.
  const goToPage = (e: MouseEvent, n: number) => {
    if (!isPlainClick(e)) return;
    e.preventDefault();
    page = n;
  };

  const start = $derived((page - 1) * pageSize);
  const shown = $derived(items.length);

  // As in app.html, which only covers the first page load
  const title = `${SITE_NAME} — Cerca i descobreix els episodis del programa`;
  const isFilteredView = $derived(hasFilters);
  const canonicalUrl = $derived(
    page === initialPage ? `${SITE_URL}/` : `${SITE_URL}/?page=${page}`
  );
  const prevUrl = $derived(
    page > 1 ? (page - 1 === 1 ? `${SITE_URL}/` : `${SITE_URL}/?page=${page - 1}`) : null
  );
  const nextUrl = $derived(
    totalPages > 0 && page < totalPages ? `${SITE_URL}/?page=${page + 1}` : null
  );

  const onKeydown = (e: KeyboardEvent) => {
    const target = e.target as HTMLElement | null;
    const tag = target?.tagName;
    if (e.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA") {
      e.preventDefault();
      searchInput?.focus();
    } else if (e.key === "Escape" && document.activeElement === searchInput) {
      searchInput?.blur();
    }
  };
</script>

<svelte:window onkeydown={onKeydown} />

<svelte:head>
  <title>{title}</title>
  <link rel="canonical" href={canonicalUrl} />
  {#if isFilteredView}
    <meta name="robots" content="noindex,follow" />
  {/if}
  {#if prevUrl}
    <link rel="prev" href={prevUrl} />
  {/if}
  {#if nextUrl}
    <link rel="next" href={nextUrl} />
  {/if}
</svelte:head>

<div class="mx-auto w-full max-w-screen-xl px-6 pt-8 pb-12 md:px-10 md:pt-14">
  <AppHero>
    <a
      href="/mapa"
      class="mt-4 inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.1em] text-vermillion-deep hover:text-ink"
    >
      <MapIcon class="size-3.5" />
      Explora el mapa
    </a>
  </AppHero>

  {#snippet facetPanel()}
    <Facet
      label="Temes"
      placeholder="Cerca un tema…"
      type="topic"
      items={topicItems}
      selected={categories.topic}
      onToggle={(slug) => toggleCategory("topic", slug)}
      matchAll={matchAll.includes("topic")}
      onMatchAllChange={(all) => setMatchAll("topic", all)}
      loading={topicsQuery.isLoading}
      counts={facetCounts}
    />
    <Facet
      label="Llocs"
      placeholder="Cerca un lloc…"
      type="location"
      items={locationItems}
      selected={categories.location}
      onToggle={(slug) => toggleCategory("location", slug)}
      matchAll={matchAll.includes("location")}
      onMatchAllChange={(all) => setMatchAll("location", all)}
      loading={locationsQuery.isLoading}
      counts={facetCounts}
    />
    <Facet
      label="Personatges"
      placeholder="Cerca un personatge…"
      type="character"
      items={characterItems}
      selected={categories.character}
      onToggle={(slug) => toggleCategory("character", slug)}
      matchAll={matchAll.includes("character")}
      onMatchAllChange={(all) => setMatchAll("character", all)}
      loading={charactersQuery.isLoading}
      counts={facetCounts}
    />
    <Facet
      label="Èpoques"
      placeholder="Cerca una època…"
      type="time_period"
      items={timePeriodItems}
      selected={categories.time_period}
      onToggle={(slug) => toggleCategory("time_period", slug)}
      matchAll={matchAll.includes("time_period")}
      onMatchAllChange={(all) => setMatchAll("time_period", all)}
      loading={timePeriodsQuery.isLoading}
      counts={facetCounts}
    />

    <button
      type="button"
      onclick={clearAll}
      disabled={!hasFilters}
      class={cn(
        "mt-2 w-full cursor-pointer border-none bg-ink py-2.5 font-mono text-[10px] uppercase tracking-[0.14em] text-paper transition-colors",
        "hover:bg-vermillion-deep focus-visible:bg-vermillion-deep focus-visible:outline-none",
        "disabled:cursor-not-allowed disabled:bg-ink-3 disabled:opacity-40 disabled:hover:bg-ink-3"
      )}
    >
      Esborra els filtres
    </button>
  {/snippet}

  <!-- Mobile drawer (shadcn Sheet) -->
  <Sheet.Root bind:open={filtersOpen}>
    <Sheet.Content side="right" class="overflow-y-auto bg-paper px-5 pt-5 pb-10 text-ink lg:hidden">
      <Sheet.Header class="gap-0 p-0">
        <Sheet.Title class="font-serif text-xl font-semibold text-ink">Filtres</Sheet.Title>
        <Sheet.Description class="sr-only">
          Filtra els episodis per tema, lloc, personatge o època.
        </Sheet.Description>
      </Sheet.Header>
      <div class="mt-4">
        {@render facetPanel()}
      </div>
    </Sheet.Content>
  </Sheet.Root>

  <div class="mt-9 grid grid-cols-1 gap-12 lg:grid-cols-[260px_1fr]">
    <!-- Desktop sidebar -->
    <aside
      aria-label="Filtres"
      class="hidden lg:sticky lg:top-6 lg:block lg:max-h-[calc(100vh-3rem)] lg:self-start lg:overflow-y-auto"
    >
      {@render facetPanel()}
    </aside>

    <!-- Main column: a section, as the layout already has the <main> -->
    <section aria-label="Episodis" class="min-w-0">
      <!-- Search bar (+ mobile filter button) -->
      <div class="flex items-stretch gap-2">
        <div
          class="flex flex-1 items-center border border-rule bg-paper-2 px-3.5 transition-colors focus-within:border-ink focus-within:bg-paper"
        >
          {#if queryData.isFetching && !queryData.isLoading}
            <Loader class="size-4 flex-none animate-spin text-ink-3" aria-label="Cercant" />
          {:else}
            <Search class="size-4 flex-none text-ink-3" />
          {/if}
          <input
            bind:this={searchInput}
            id="search-episodes"
            type="search"
            value={searchText}
            oninput={(e) => handleSearchInput(e.currentTarget.value)}
            placeholder="Cerca per títol i descripció"
            aria-label="Cerca per títol i descripció"
            autocomplete="off"
            class="flex-1 border-0 bg-transparent px-3 py-3.5 font-serif text-[19px] text-ink outline-none placeholder:italic placeholder:text-ink-3"
          />
          <span
            class="hidden rounded-sm border border-rule bg-paper px-1.5 py-0.5 font-mono text-[10px] text-ink-3 sm:inline"
          >
            /
          </span>
        </div>
        <button
          type="button"
          onclick={() => (filtersOpen = true)}
          aria-label="Obre els filtres"
          class="relative flex flex-none cursor-pointer items-center justify-center border border-rule bg-paper-2 px-4 text-ink-2 transition-colors hover:border-ink hover:text-ink lg:hidden"
        >
          <SlidersHorizontal class="size-4" />
          {#if activeFilterCount > 0}
            <span
              class="absolute -top-1.5 -right-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-vermillion-deep px-1 font-mono text-[9px] font-medium leading-none tracking-normal text-paper"
            >
              {activeFilterCount}
            </span>
          {/if}
        </button>
      </div>

      {#if searchText.trim().length > 0 && searchText.trim().length < minSearchChars}
        <p
          class="mt-1.5 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3"
          aria-live="polite"
        >
          Cal un mínim de {minSearchChars} lletres
        </p>
      {/if}

      <!-- Result bar with sort -->
      <div
        class="mt-5 mb-2.5 flex flex-wrap items-baseline justify-between gap-3 border-b border-rule pb-2 font-mono text-[11px] uppercase tracking-[0.1em] text-ink-3"
      >
        <div>
          <strong
            class="mr-1.5 font-serif text-lg font-semibold tracking-normal text-ink normal-case"
          >
            {total.toLocaleString("ca")}
          </strong>
          episodis trobats
        </div>
        <div class="flex items-center gap-4">
          <span>Ordena</span>
          {#each [{ id: "desc" as const, label: "Més recents" }, { id: "asc" as const, label: "Més antics" }] as opt (opt.id)}
            <button
              type="button"
              onclick={() => {
                order = opt.id;
                page = 1;
              }}
              class={cn(
                "cursor-pointer border-0 bg-transparent p-0.5 font-mono text-[11px] uppercase tracking-[0.1em] text-ink-3 hover:text-ink",
                order === opt.id && "border-b border-vermillion pb-0.5 text-ink"
              )}>{opt.label}</button
            >
          {/each}
        </div>
      </div>

      <!-- Table -->
      {#if queryData.isLoading}
        <table class="w-full border-collapse font-body">
          <thead>
            <tr>
              <th
                class="hidden border-b border-rule px-3 py-3 pl-0 text-left font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-ink-3 md:table-cell md:w-[110px]"
              >
                Emissió
              </th>
              <th
                class="border-b border-rule py-3 pr-3 pl-0 text-left font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-ink-3 md:pl-3"
              >
                Títol &amp; sinopsi
              </th>
              <th
                class="hidden border-b border-rule px-3 py-3 pr-0 text-left font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-ink-3 lg:table-cell"
                style="width: 38%"
              >
                Categories
              </th>
            </tr>
          </thead>
          <tbody aria-busy="true" aria-label="Carregant episodis">
            {#each Array.from({ length: pageSize }) as _, i (i)}
              <tr class="animate-pulse border-b border-rule">
                <td class="hidden px-3 pt-4.5 pb-4 pl-0 align-top md:table-cell md:w-[110px]">
                  <span class="block h-5 w-8 rounded-sm bg-paper-edge"></span>
                  <span class="mt-2 block h-2.5 w-14 rounded-sm bg-paper-edge/70"></span>
                </td>
                <td class="py-4 pr-3 pl-0 align-top md:pl-3">
                  <span class="mb-2 block h-2.5 w-20 rounded-sm bg-paper-edge/70 md:hidden"></span>
                  <span
                    class="mb-2 block h-5 rounded-sm bg-paper-edge"
                    style:width="{45 + ((i * 7) % 40)}%"
                  ></span>
                  <span class="mb-1.5 block h-3 w-[92%] rounded-sm bg-paper-edge/70"></span>
                  <span
                    class="block h-3 rounded-sm bg-paper-edge/70"
                    style:width="{60 + ((i * 11) % 25)}%"
                  ></span>
                </td>
                <td class="hidden px-3 py-4 pr-0 align-top lg:table-cell" style="width: 38%">
                  <div class="flex flex-wrap gap-1.5">
                    <span class="h-5 w-20 rounded-sm bg-paper-edge/80"></span>
                    <span class="h-5 w-28 rounded-sm bg-paper-edge/80"></span>
                    {#if i % 3 !== 0}
                      <span class="h-5 w-16 rounded-sm bg-paper-edge/80"></span>
                    {/if}
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {:else if items.length === 0}
        <div class="px-5 py-20 text-center text-ink-3">
          <h2 class="mb-2 font-serif text-3xl font-medium italic text-ink-2">
            Cap episodi a la lleixa
          </h2>
          <p class="mb-5 text-sm">Prova d'esborrar algun filtre o de canviar la cerca.</p>
          <button
            type="button"
            onclick={clearAll}
            class="cursor-pointer bg-ink px-6 py-2.5 font-mono text-[10px] uppercase tracking-[0.14em] text-paper hover:bg-vermillion-deep"
          >
            Torna a començar
          </button>
        </div>
      {:else}
        {#snippet categoryChip(c: CategoryBase)}
          <CategoryChip
            type={c.type}
            name={c.name}
            active={isSelected(c)}
            onclick={() => toggleCategory(c.type as CategoryType, c.slug)}
          />
        {/snippet}

        <table class="w-full border-collapse font-body">
          <thead>
            <tr>
              <th
                class="hidden border-b border-rule px-3 py-3 pl-0 text-left font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-ink-3 md:table-cell md:w-[110px]"
              >
                Emissió
              </th>
              <th
                class="border-b border-rule py-3 pr-3 pl-0 text-left font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-ink-3 md:pl-3"
              >
                Títol &amp; sinopsi
              </th>
              <th
                class="hidden border-b border-rule px-3 py-3 pr-0 text-left font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-ink-3 lg:table-cell"
                style="width: 38%"
              >
                Categories
              </th>
            </tr>
          </thead>
          <tbody>
            {#each processedItems as p (p.ep.id)}
              {@const ep = p.ep}
              {@const d = ep.published_at ? fmtDate(ep.published_at) : null}
              <!-- Safari won't anchor the title's overlay on a <tr>, so it covered
                   the page and every tap opened the last row; clipped to the row -->
              <tr
                class="group relative border-b border-rule [clip-path:inset(0)] [transform:translate(0)]"
              >
                <td
                  class="hidden px-3 pt-4.5 pb-4 pl-0 align-top font-mono text-[11px] whitespace-nowrap text-ink-2 md:table-cell md:w-[110px]"
                >
                  {#if d}
                    <span class="block font-serif text-[22px] leading-none font-semibold text-ink"
                      >{d.day}</span
                    >
                    <span class="mt-1 block text-[10px] uppercase tracking-[0.1em] text-ink-3"
                      >{d.my}</span
                    >
                  {/if}
                </td>
                <td class="py-4 pr-3 pl-0 align-top md:pl-3">
                  <!-- Without the Emissió column, the date above the title -->
                  {#if d}
                    <span
                      class="mb-1 block font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3 md:hidden"
                      >{d.day} {d.my}</span
                    >
                  {/if}
                  <a
                    href={`/episodis/${ep.id}/${ep.slug}`}
                    class="row-link mb-1.5 block font-serif text-[21px] leading-tight font-semibold text-ink no-underline transition-colors group-hover:text-vermillion-deep focus-visible:text-vermillion-deep before:absolute before:inset-0 before:content-['']"
                  >
                    {#each p.titleChunks as c, i (i)}
                      {#if c.match}
                        <mark class="bg-vermillion/20 px-0.5 text-ink">{c.text}</mark>
                      {:else}{c.text}{/if}
                    {/each}
                  </a>
                  {#if p.descShown}
                    <span class="line-clamp-2 text-[15px] md:text-[13.5px] leading-snug text-ink-2">
                      {#each p.descChunks as c, i (i)}
                        {#if c.match}
                          <mark class="bg-vermillion/20 px-0.5 text-ink">{c.text}</mark>
                        {:else}{c.text}{/if}
                      {/each}
                    </span>
                  {/if}
                  <!-- Without the Categories column, the first few under the title -->
                  {#if ep.categories?.length}
                    {@const expanded = expandedRows.has(ep.id)}
                    {@const ordered = tickedFirst(ep.categories)}
                    <div class="relative z-10 mt-2.5 flex flex-wrap gap-1.5 lg:hidden">
                      {#each expanded ? ordered : ordered.slice(0, 3) as c (c.id)}
                        {@render categoryChip(c)}
                      {/each}
                      {#if !expanded && ep.categories.length > 3}
                        <button
                          type="button"
                          onclick={() => expandedRows.add(ep.id)}
                          class="inline-flex cursor-pointer items-center rounded-sm border border-rule px-1.5 py-0.5 font-mono text-[10px] leading-snug tracking-[0.05em] text-ink-3 hover:border-ink-3 hover:text-ink"
                          aria-label={`Mostra ${ep.categories.length - 3} categories més`}
                          >+{ep.categories.length - 3}</button
                        >
                      {/if}
                    </div>
                  {/if}
                </td>
                <td class="hidden px-3 py-4 pr-0 align-top lg:table-cell" style="width: 38%">
                  <div class="relative z-10 flex flex-wrap gap-1.5">
                    {#each ep.categories ?? [] as c (c.id)}
                      {@render categoryChip(c)}
                    {/each}
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>

        <!-- Pagination -->
        {#if totalPages > 1}
          {@const pageClass =
            "inline-flex h-7.5 min-w-9 items-center justify-center gap-1.5 rounded-sm border border-rule bg-paper-2 px-3 font-mono text-[11px] uppercase tracking-[0.08em] text-ink-2 transition-colors hover:border-ink hover:text-ink"}
          {@const pageOffClass = cn(
            pageClass,
            "cursor-not-allowed opacity-35 hover:border-rule hover:text-ink-2"
          )}
          <nav
            class="@container mt-7 flex flex-wrap items-center justify-between gap-6 border-t border-rule pt-4 font-mono text-[11px] uppercase tracking-[0.08em] text-ink-3"
            aria-label="Paginació"
          >
            <div class="flex-1 whitespace-nowrap">
              {start + 1}–{start + shown} de {total.toLocaleString("ca")}
            </div>
            <div class="flex items-center gap-1">
              {#if page > 1}
                <a
                  href={pageHref(page - 1)}
                  onclick={(e) => goToPage(e, page - 1)}
                  rel="prev"
                  aria-label="Pàgina anterior"
                  class={pageClass}
                  ><ChevronLeft class="size-3.5" /><span class="@max-xl:hidden @2xl:@max-3xl:hidden"
                    >Anterior</span
                  ></a
                >
              {:else}
                <span aria-disabled="true" class={pageOffClass}
                  ><ChevronLeft class="size-3.5" /><span class="@max-xl:hidden @2xl:@max-3xl:hidden"
                    >Anterior</span
                  ></span
                >
              {/if}
              <!-- Sized by the nav, not the viewport: the lg sidebar narrows it -->
              <span class="px-2 whitespace-nowrap @2xl:hidden">pàg. {page} de {totalPages}</span>
              {#each pageNumbers as p, i (i)}
                {#if p === "…"}
                  <span class="px-1.5 text-ink-3 @max-2xl:hidden">…</span>
                {:else}
                  <a
                    href={pageHref(p)}
                    onclick={(e) => goToPage(e, p)}
                    aria-current={p === page ? "page" : undefined}
                    class={cn(
                      pageClass,
                      "@max-2xl:hidden",
                      p === page && "border-ink bg-ink text-paper hover:bg-ink hover:text-paper"
                    )}
                  >
                    {p}
                  </a>
                {/if}
              {/each}
              {#if page < totalPages}
                <a
                  href={pageHref(page + 1)}
                  onclick={(e) => goToPage(e, page + 1)}
                  rel="next"
                  aria-label="Pàgina següent"
                  class={pageClass}
                >
                  <span class="@max-xl:hidden @2xl:@max-3xl:hidden">Següent</span><ChevronRight
                    class="size-3.5"
                  />
                </a>
              {:else}
                <span aria-disabled="true" class={pageOffClass}>
                  <span class="@max-xl:hidden @2xl:@max-3xl:hidden">Següent</span><ChevronRight
                    class="size-3.5"
                  />
                </span>
              {/if}
            </div>
          </nav>
        {/if}
      {/if}
    </section>
  </div>
</div>

<style>
  .row-link:focus-visible {
    outline: none;
  }
  .row-link:focus-visible::before {
    outline: 1px solid var(--color-vermillion);
  }
</style>
