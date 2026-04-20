<script lang="ts">
  import { onMount, untrack } from "svelte";
  import { SvelteURLSearchParams } from "svelte/reactivity";

  import { goto } from "$app/navigation";
  import { page as pageStore } from "$app/state";
  import { LoaderCircleIcon, Search } from "@lucide/svelte";
  import { createInfiniteQuery, createQuery } from "@tanstack/svelte-query";

  import {
    type Category,
    type CategoryType,
    getCategoriesApiCategoriesGet,
    getEpisodesApiEpisodesGet,
  } from "client";

  import AppHero from "lib/components/app-hero.svelte";
  import { CATEGORY_TYPE_COLORS, CATEGORY_TYPE_LABELS, cn, hasDescription } from "lib/utils";

  import Facet from "./facet.svelte";

  const initialPage = 1;
  const defaultPageSize = 20;
  const maxPageSize = 50;

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

  let searchQuery = $state("");
  let page = $state(initialPage);
  let pageSize = $state(defaultPageSize);
  let categories = $state<Record<CategoryType, number[]>>({
    topic: [],
    character: [],
    location: [],
    time_period: [],
  });
  let order = $state<"asc" | "desc">("desc");
  let searchInput: HTMLInputElement | null = $state(null);

  let isInitialized = false;
  onMount(() => {
    const params = pageStore.url.searchParams;

    const urlPage = params.get("page");
    if (urlPage) {
      const n = Number.parseInt(urlPage, 10);
      if (!Number.isNaN(n) && n > 0) page = n;
    }

    const urlPageSize = params.get("pageSize");
    if (urlPageSize) {
      const n = Number.parseInt(urlPageSize, 10);
      if (!Number.isNaN(n) && n > 0 && n <= maxPageSize) pageSize = n;
    }

    const urlSearch = params.get("search");
    if (urlSearch) searchQuery = urlSearch;

    const urlOrder = params.get("order");
    if (urlOrder === "asc" || urlOrder === "desc") {
      order = urlOrder;
    }

    isInitialized = true;
  });

  let urlTimer: ReturnType<typeof setTimeout> | null = null;
  const updateUrl = () => {
    if (!isInitialized) return;
    if (urlTimer) clearTimeout(urlTimer);
    urlTimer = setTimeout(() => {
      const params = new SvelteURLSearchParams(pageStore.url.searchParams);

      if (searchQuery) params.set("search", searchQuery);
      else params.delete("search");

      if (order !== "desc") params.set("order", order);
      else params.delete("order");

      if (page !== initialPage) params.set("page", String(page));
      else params.delete("page");

      if (pageSize !== defaultPageSize) params.set("pageSize", String(pageSize));
      else params.delete("pageSize");

      const qs = params.toString();
      goto(qs ? `?${qs}` : pageStore.url.pathname, {
        replaceState: true,
        noScroll: true,
        keepFocus: true,
      });
    }, 100);
  };

  $effect(() => {
    page; // eslint-disable-line @typescript-eslint/no-unused-expressions
    pageSize; // eslint-disable-line @typescript-eslint/no-unused-expressions
    searchQuery; // eslint-disable-line @typescript-eslint/no-unused-expressions
    order; // eslint-disable-line @typescript-eslint/no-unused-expressions
    if (isInitialized) updateUrl();
  });

  let searchTimer: ReturnType<typeof setTimeout> | null = null;
  const handleSearchInput = (value: string) => {
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      searchQuery = value;
      page = 1;
    }, 300);
  };

  const toggleCategory = (type: CategoryType, id: number) => {
    const current = categories[type];
    const exists = current.includes(id);
    categories = {
      ...categories,
      [type]: exists ? current.filter((c) => c !== id) : [...current, id],
    };
    page = 1;
  };

  const removeCategory = (type: CategoryType, id: number) => {
    categories = { ...categories, [type]: categories[type].filter((c) => c !== id) };
    page = 1;
  };

  const clearAll = () => {
    categories = { topic: [], character: [], location: [], time_period: [] };
    searchQuery = "";
    if (searchInput) searchInput.value = "";
    page = 1;
  };

  const categoriesString = $derived(Object.values(categories).flat().join(","));

  const queryData = createQuery(() => ({
    queryKey: ["episodes", searchQuery, page, pageSize, order, categoriesString],
    queryFn: () =>
      getEpisodesApiEpisodesGet({
        query: {
          search: searchQuery,
          page,
          size: pageSize,
          order,
          categories: categoriesString,
        },
      }),
    // placeholderData: keepPreviousData,
    staleTime: 1000 * 30,
  }));

  const items = $derived(queryData.data?.data?.items ?? []);
  const total = $derived(queryData.data?.data?.total ?? 0);
  const totalPages = $derived(queryData.data?.data?.pages ?? 0);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const getNextPageParam = (lastPage: any) => {
    const data = lastPage.data;
    if (data.page && data.pages && data.page < data.pages) return data.page + 1;
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

  const mapItems = (cats: Category[]) =>
    cats
      .filter((c) => c.id != null)
      .map((c) => ({ id: c.id as number, name: c.name, count: c.count ?? 0 }))
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

  const findItem = (type: CategoryType, id: number) =>
    allCategoryItems[type].find((i) => i.id === id);

  const hasFilters = $derived(!!searchQuery || ALL_TYPES.some((t) => categories[t].length > 0));

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

  const start = $derived((page - 1) * pageSize);
  const shown = $derived(items.length);

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

<div class="mx-auto w-full max-w-screen-xl px-6 pt-8 pb-12 md:px-10 md:pt-14">
  <AppHero />

  <div class="mt-9 grid grid-cols-1 gap-12 lg:grid-cols-[260px_1fr]">
    <!-- Sidebar -->
    <aside
      class="lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] lg:self-start lg:overflow-y-auto lg:pr-2"
    >
      <Facet
        label="Temes"
        placeholder="Cerca un tema…"
        type="topic"
        items={topicItems}
        selected={categories.topic}
        onToggle={(id) => toggleCategory("topic", id)}
      />
      <Facet
        label="Llocs"
        placeholder="Cerca un lloc…"
        type="location"
        items={locationItems}
        selected={categories.location}
        onToggle={(id) => toggleCategory("location", id)}
      />
      <Facet
        label="Personatges"
        placeholder="Cerca un personatge…"
        type="character"
        items={characterItems}
        selected={categories.character}
        onToggle={(id) => toggleCategory("character", id)}
      />
      <Facet
        label="Èpoques"
        type="time_period"
        items={timePeriodItems}
        selected={categories.time_period}
        onToggle={(id) => toggleCategory("time_period", id)}
        showSearch={false}
      />

      <button
        type="button"
        onclick={clearAll}
        disabled={!hasFilters}
        class={cn(
          "mt-2 w-full cursor-pointer border-none bg-ink py-2.5 font-mono text-[10px] uppercase tracking-[0.14em] text-paper transition-colors",
          "hover:bg-vermillion-deep",
          "disabled:cursor-not-allowed disabled:bg-ink-3 disabled:opacity-40 disabled:hover:bg-ink-3"
        )}
      >
        Esborra els filtres
      </button>
    </aside>

    <!-- Main column -->
    <main class="min-w-0">
      <!-- Search bar -->
      <div
        class="flex items-center border border-rule bg-white/40 px-3.5 transition-colors focus-within:border-ink focus-within:bg-white/60"
      >
        <Search class="size-4 flex-none text-ink-3" />
        <input
          bind:this={searchInput}
          type="search"
          value={searchQuery}
          oninput={(e) => handleSearchInput(e.currentTarget.value)}
          placeholder="Cerqueu per títol, descripció o personatge…"
          autocomplete="off"
          class="flex-1 border-0 bg-transparent px-3 py-3.5 font-serif text-[19px] text-ink outline-none placeholder:italic placeholder:text-ink-3"
        />
        <span
          class="hidden rounded-sm border border-rule bg-paper px-1.5 py-0.5 font-mono text-[10px] text-ink-3 sm:inline"
        >
          /
        </span>
      </div>

      <!-- Active filter chips -->
      {#if hasFilters}
        <div class="mt-3 flex flex-wrap gap-1.5">
          {#if searchQuery}
            <span
              class="inline-flex items-center gap-1.5 border border-paper-edge bg-paper-2 py-1 pr-1.5 pl-2 font-mono text-[12px] uppercase tracking-[0.05em] text-ink-2"
            >
              cerca: "{searchQuery}"
              <button
                type="button"
                aria-label="Esborra cerca"
                onclick={() => {
                  searchQuery = "";
                  if (searchInput) searchInput.value = "";
                  page = 1;
                }}
                class="cursor-pointer px-0.5 text-[14px] leading-none text-ink-3 hover:text-vermillion-deep"
                >×</button
              >
            </span>
          {/if}
          {#each ALL_TYPES as type (type)}
            {#each categories[type] as id (`${type}-${id}`)}
              {@const item = findItem(type, id)}
              {#if item}
                <span
                  class="inline-flex items-center gap-1.5 border border-paper-edge bg-paper-2 py-1 pr-1.5 pl-2 font-mono text-[12px] uppercase tracking-[0.05em] text-ink-2"
                >
                  <span class="size-1.5 rounded-full" style:background={CATEGORY_TYPE_COLORS[type]}
                  ></span>
                  {item.name}
                  <button
                    type="button"
                    aria-label={`Treu ${item.name}`}
                    onclick={() => removeCategory(type, id)}
                    class="cursor-pointer px-0.5 text-[14px] leading-none text-ink-3 hover:text-vermillion-deep"
                    >×</button
                  >
                </span>
              {/if}
            {/each}
          {/each}
        </div>
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
                "cursor-pointer border-0 bg-transparent p-0 font-mono text-[11px] uppercase tracking-[0.1em] text-ink-3 hover:text-ink",
                order === opt.id && "border-b border-vermillion pb-0.5 text-ink"
              )}>{opt.label}</button
            >
          {/each}
        </div>
      </div>

      <!-- Table -->
      {#if queryData.isLoading}
        <div class="flex justify-center py-20">
          <LoaderCircleIcon class="size-6 animate-spin text-ink-3" />
        </div>
      {:else if items.length === 0}
        <div class="px-5 py-20 text-center text-ink-3">
          <h2 class="mb-2 font-serif text-3xl font-medium italic text-ink-2">
            Cap episodi a la lleixa
          </h2>
          <p class="mb-5 text-sm">Proveu d'esborrar algun filtre o de canviar la cerca.</p>
          <button
            type="button"
            onclick={clearAll}
            class="cursor-pointer bg-ink px-6 py-2.5 font-mono text-[10px] uppercase tracking-[0.14em] text-paper hover:bg-vermillion-deep"
          >
            Tornar a començar
          </button>
        </div>
      {:else}
        <table class="w-full border-collapse font-body">
          <thead>
            <tr>
              <th
                class="border-b border-rule px-3 py-3 pl-0 text-left font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-ink-3"
                style="width: 110px"
              >
                Emissió
              </th>
              <th
                class="border-b border-rule px-3 py-3 text-left font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-ink-3"
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
            {#each items as ep (ep.id)}
              {@const d = ep.published_at ? fmtDate(ep.published_at) : null}
              <tr
                class="group cursor-pointer border-b border-rule transition-colors hover:bg-vermillion/5"
                onclick={() => goto(`/episodis/${ep.id}/${ep.slug}`)}
              >
                <td
                  class="px-3 pt-4.5 pb-4 pl-0 align-top font-mono text-[11px] whitespace-nowrap text-ink-2"
                  style="width: 110px"
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
                <td class="px-3 py-4 align-top">
                  <span
                    class="mb-1.5 block font-serif text-[21px] leading-tight font-semibold text-ink transition-colors group-hover:text-vermillion-deep"
                  >
                    {ep.title}
                  </span>
                  <span class="line-clamp-2 text-[13.5px] leading-snug text-ink-2">
                    {hasDescription(ep.description) ? ep.description : ""}
                  </span>
                </td>
                <td
                  class="hidden px-3 py-4 pr-0 align-top lg:table-cell"
                  style="width: 38%"
                  onclick={(e) => e.stopPropagation()}
                >
                  <div class="flex flex-wrap gap-1.5">
                    {#each ep.categories ?? [] as c (c.id)}
                      <button
                        type="button"
                        title={CATEGORY_TYPE_LABELS[c.type as CategoryType] ?? ""}
                        onclick={() => toggleCategory(c.type as CategoryType, c.id)}
                        class={cn(
                          "inline-flex cursor-pointer items-center gap-1.5 rounded-sm border bg-white/40 px-2 py-0.5 font-mono text-[10px] leading-snug uppercase tracking-[0.05em] whitespace-nowrap transition-transform hover:-translate-y-[1px]",
                          {
                            "border-vermillion-deep/30 text-vermillion-deep": c.type === "topic",
                            "border-teal/30 text-teal": c.type === "location",
                            "border-character/30 text-character": c.type === "character",
                            "border-plum/30 text-plum": c.type === "time_period",
                          }
                        )}
                      >
                        <span
                          class="size-1.5 rounded-full"
                          style:background="currentColor"
                          style:opacity="0.9"
                        ></span>
                        {c.name}
                      </button>
                    {/each}
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>

        <!-- Pagination -->
        {#if totalPages > 1 || pageSize !== defaultPageSize}
          <nav
            class="mt-7 flex flex-wrap items-center justify-between gap-6 border-t border-rule pt-4 font-mono text-[11px] uppercase tracking-[0.08em] text-ink-3"
            aria-label="Paginació"
          >
            <div class="flex-1">
              {start + 1}–{start + shown} de {total.toLocaleString("ca")}
            </div>
            {#if totalPages > 1}
              <div class="flex items-center gap-1">
                <button
                  type="button"
                  onclick={() => (page = Math.max(1, page - 1))}
                  disabled={page === 1}
                  class="min-w-9 cursor-pointer rounded-sm border border-rule bg-white/40 px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.08em] text-ink-2 transition-colors hover:border-ink hover:text-ink disabled:cursor-not-allowed disabled:opacity-35"
                >
                  ← Anterior
                </button>
                {#each pageNumbers as p, i (i)}
                  {#if p === "…"}
                    <span class="px-1.5 text-ink-3">…</span>
                  {:else}
                    <button
                      type="button"
                      onclick={() => (page = p)}
                      class={cn(
                        "min-w-9 cursor-pointer rounded-sm border border-rule bg-white/40 px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.08em] text-ink-2 transition-colors hover:border-ink hover:text-ink",
                        p === page && "border-ink bg-ink text-paper hover:bg-ink hover:text-paper"
                      )}>{p}</button
                    >
                  {/if}
                {/each}
                <button
                  type="button"
                  onclick={() => (page = Math.min(totalPages, page + 1))}
                  disabled={page === totalPages}
                  class="min-w-9 cursor-pointer rounded-sm border border-rule bg-white/40 px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.08em] text-ink-2 transition-colors hover:border-ink hover:text-ink disabled:cursor-not-allowed disabled:opacity-35"
                >
                  Següent →
                </button>
              </div>
            {/if}
            <label class="flex items-center gap-2">
              Per pàgina
              <select
                value={pageSize}
                onchange={(e) => {
                  pageSize = Number(e.currentTarget.value);
                  page = 1;
                }}
                class="cursor-pointer rounded-sm border border-rule bg-white/40 px-2 py-1.5 font-mono text-[11px] uppercase tracking-[0.06em] text-ink focus:border-vermillion focus:outline-none"
              >
                {#each [10, 20, 30, 50] as opt (opt)}
                  <option value={opt}>{opt}</option>
                {/each}
              </select>
            </label>
          </nav>
        {/if}
      {/if}
    </main>
  </div>
</div>
