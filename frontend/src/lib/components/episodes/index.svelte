<script lang="ts">
  import { onMount } from "svelte";
  import { SvelteURLSearchParams } from "svelte/reactivity";

  import { goto } from "$app/navigation";
  import { page as pageStore } from "$app/state";
  import { LoaderCircleIcon, Search, Trash2Icon } from "@lucide/svelte";
  import { createInfiniteQuery, createQuery, keepPreviousData } from "@tanstack/svelte-query";
  import {
    type PaginationState,
    type RowSelectionState,
    type SortingState,
    type Updater,
    getCoreRowModel,
    getSortedRowModel,
  } from "@tanstack/table-core";

  import {
    type Category,
    type CategoryType,
    getCategoriesApiCategoriesGet,
    getEpisodesApiEpisodesGet,
  } from "client";

  import AppHero from "lib/components/app-hero.svelte";
  import { Button } from "lib/components/ui/button";
  import { FlexRender, createSvelteTable } from "lib/components/ui/data-table";
  import DataTableHeader from "lib/components/ui/data-table/data-table-header.svelte";
  import DataTablePagination from "lib/components/ui/data-table/data-table-pagination.svelte";
  import Input from "lib/components/ui/input.svelte";
  import * as Table from "lib/components/ui/table";
  import { debounce } from "lib/hooks/use-debounce";

  import { columns } from "./columns";
  import Filter from "./filter.svelte";

  const initialPage = 1;
  const defaultPageSize = 20;
  const maxPageSize = 50;

  // Initialize stores
  let searchQuery = $state("");
  let page = $state(initialPage);
  let pageSize = $state(defaultPageSize);
  let categories = $state<Record<CategoryType, string[]>>({
    topic: [],
    character: [],
    location: [],
    time_period: [],
  });
  let sorting = $state<SortingState>([{ id: "published_at", desc: true }]);
  let rowSelection = $state<RowSelectionState>({});
  const order = $derived.by(() => {
    const column = sorting.find((v) => v.id === "published_at");
    if (!column) return "desc";
    return column.desc ? "desc" : "asc";
  });

  // Initialize from URL on mount
  let isInitialized = false;
  onMount(() => {
    const params = pageStore.url.searchParams;

    const urlPage = params.get("page");
    if (urlPage) {
      const pageNum = Number.parseInt(urlPage, 10);
      if (!Number.isNaN(pageNum) && pageNum > 0) {
        page = pageNum;
      }
    }

    const urlPageSize = params.get("pageSize");
    if (urlPageSize) {
      const size = Number.parseInt(urlPageSize, 10);
      if (!Number.isNaN(size) && size > 0 && size <= maxPageSize) {
        pageSize = size;
      }
    }

    const urlSearch = params.get("search");
    if (urlSearch) {
      searchQuery = urlSearch;
    }

    const urlOrder = params.get("order");
    if (urlOrder) {
      sorting = [{ id: "published_at", desc: urlOrder === "desc" }];
    }

    isInitialized = true;
  });

  const updateUrl = debounce(() => {
    if (!isInitialized) return;

    const params = new SvelteURLSearchParams(pageStore.url.searchParams);

    if (searchQuery) {
      params.set("search", searchQuery);
    } else {
      params.delete("search");
    }

    if (order !== "desc") {
      params.set("order", order);
    } else {
      params.delete("order");
    }

    if (page !== initialPage) {
      params.set("page", String(page));
    } else {
      params.delete("page");
    }

    if (pageSize !== defaultPageSize) {
      params.set("pageSize", String(pageSize));
    } else {
      params.delete("pageSize");
    }

    goto(`?${params.toString()}`, {
      replaceState: true,
      noScroll: true,
      keepFocus: true,
    });
  }, 100);

  $effect(() => {
    page; // eslint-disable-line @typescript-eslint/no-unused-expressions
    pageSize; // eslint-disable-line @typescript-eslint/no-unused-expressions
    searchQuery; // eslint-disable-line @typescript-eslint/no-unused-expressions
    order; // eslint-disable-line @typescript-eslint/no-unused-expressions

    if (isInitialized) {
      updateUrl();
    }
  });

  const debouncedSearch = debounce((value: string) => {
    searchQuery = value;
    page = 1; // Reset page when search changes
  }, 300);

  const handleSortingChange = (state: Updater<SortingState>) => {
    const newSorting = typeof state === "function" ? state(table.getState().sorting) : state;
    sorting = newSorting as SortingState;
  };

  const handleCategoriesChange = (type: CategoryType, newCategories: string[]) => {
    categories = {
      ...categories,
      [type]: newCategories,
    };
    page = 1;
  };

  const handlePaginationChange = (pagination: Updater<PaginationState>) => {
    const newPagination =
      typeof pagination === "function" ? pagination(table.getState().pagination) : pagination;
    page = newPagination.pageIndex + 1;
    pageSize = newPagination.pageSize;
  };

  const categoriesString = $derived.by(() => Object.values(categories).flat().join(","));

  const queryData = createQuery(() => {
    return {
      queryKey: ["episodes", searchQuery, page, pageSize, order, categoriesString],
      queryFn: () =>
        getEpisodesApiEpisodesGet({
          query: {
            search: searchQuery,
            page: page,
            size: pageSize,
            order: order || undefined,
            categories: categoriesString,
          },
        }),
      placeholderData: keepPreviousData,
    };
  });

  const table = $derived(
    createSvelteTable({
      data: queryData.data?.data?.items ?? [],
      columns,
      getCoreRowModel: getCoreRowModel(),
      getSortedRowModel: getSortedRowModel(),
      manualSorting: true,
      manualPagination: true,
      enableRowSelection: true,
      onSortingChange: handleSortingChange,
      onPaginationChange: handlePaginationChange,
      pageCount: queryData.data?.data?.pages ?? 0,
      state: {
        sorting: sorting,
        pagination: { pageIndex: page - 1, pageSize: pageSize },
        rowSelection: rowSelection,
      },
      defaultColumn: {
        size: 300,
        minSize: 150,
      },
    })
  );

  const clearCategories = () => {
    categories = { topic: [], character: [], location: [], time_period: [] };
    page = 1;
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const getNextPageParam = (lastPage: any) => {
    const data = lastPage.data;
    if (data.page && data.pages && data.page < data.pages) {
      return data.page + 1;
    }
    return undefined;
  };

  const locationsQuery = createInfiniteQuery(() => ({
    queryKey: ["locations"],
    queryFn: ({ pageParam }) =>
      getCategoriesApiCategoriesGet({ query: { type: "location", page: pageParam, size: 500 } }),
    getNextPageParam,
    initialPageParam: 1,
    staleTime: 1000 * 60 * 10, // 10 minutes
  }));

  const topicsQuery = createInfiniteQuery(() => ({
    queryKey: ["topics"],
    queryFn: ({ pageParam }) =>
      getCategoriesApiCategoriesGet({ query: { type: "topic", page: pageParam, size: 1000 } }),
    getNextPageParam,
    initialPageParam: 1,
    staleTime: 1000 * 60 * 10, // 10 minutes
  }));

  const charactersQuery = createInfiniteQuery(() => ({
    queryKey: ["characters"],
    queryFn: ({ pageParam }) =>
      getCategoriesApiCategoriesGet({ query: { type: "character", page: pageParam, size: 500 } }),
    getNextPageParam,
    initialPageParam: 1,
    staleTime: 1000 * 60 * 10, // 10 minutes
  }));

  const timePeriodsQuery = createInfiniteQuery(() => ({
    queryKey: ["timePeriods"],
    queryFn: ({ pageParam }) =>
      getCategoriesApiCategoriesGet({ query: { type: "time_period", page: pageParam, size: 500 } }),
    getNextPageParam,
    initialPageParam: 1,
    staleTime: 1000 * 60 * 10, // 10 minutes
  }));

  const mapCategoriesDataToOptions = (category: Category[]) => {
    return category.map(({ id, name }) => ({ value: String(id), label: name }));
  };

  const locations = $derived.by(
    () =>
      locationsQuery.data?.pages.flatMap((page) =>
        mapCategoriesDataToOptions(page?.data?.items ?? [])
      ) ?? []
  );

  const topics = $derived.by(
    () =>
      topicsQuery.data?.pages.flatMap((page) =>
        mapCategoriesDataToOptions(page?.data?.items ?? [])
      ) ?? []
  );

  const characters = $derived.by(
    () =>
      charactersQuery.data?.pages.flatMap((page) =>
        mapCategoriesDataToOptions(page?.data?.items ?? [])
      ) ?? []
  );

  const timePeriods = $derived.by(
    () =>
      timePeriodsQuery.data?.pages.flatMap((page) =>
        mapCategoriesDataToOptions(page?.data?.items ?? [])
      ) ?? []
  );

  // Auto-fetch all pages when query loads
  $effect(() => {
    if (locationsQuery.data && locationsQuery.hasNextPage && !locationsQuery.isFetchingNextPage) {
      locationsQuery.fetchNextPage();
    }
  });

  $effect(() => {
    if (topicsQuery.data && topicsQuery.hasNextPage && !topicsQuery.isFetchingNextPage) {
      topicsQuery.fetchNextPage();
    }
  });

  $effect(() => {
    if (
      charactersQuery.data &&
      charactersQuery.hasNextPage &&
      !charactersQuery.isFetchingNextPage
    ) {
      charactersQuery.fetchNextPage();
    }
  });

  $effect(() => {
    if (
      timePeriodsQuery.data &&
      timePeriodsQuery.hasNextPage &&
      !timePeriodsQuery.isFetchingNextPage
    ) {
      timePeriodsQuery.fetchNextPage();
    }
  });

  const hasCategories = $derived.by(() =>
    Object.values(categories).some((categories) => categories.length > 0)
  );
</script>

<div class="xl:max-w-screen-xl mx-auto w-full">
  <AppHero />
  <div class="mb-6 space-y-4">
    <!-- Search (primary) -->
    <div class="flex justify-center">
      <div class="relative w-full max-w-xl">
        <Input
          type="search"
          class="w-full pl-9 h-12"
          placeholder="Cerca un episodi"
          value={searchQuery}
          oninput={(e) => debouncedSearch(e.currentTarget.value)}
        />
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
      </div>
    </div>

    <!-- Filters (secondary) -->
    <div class="flex flex-wrap items-center gap-4 justify-center px-3 py-2">
      <Filter
        label="Temàtica"
        type="topic"
        items={topics}
        selectedCategories={categories.topic}
        onSelect={(newCategories) => handleCategoriesChange("topic", newCategories)}
      />
      <Filter
        label="Localització"
        type="location"
        items={locations}
        selectedCategories={categories.location}
        onSelect={(newCategories) => handleCategoriesChange("location", newCategories)}
      />
      <Filter
        label="Personatge"
        type="character"
        items={characters}
        selectedCategories={categories.character}
        onSelect={(newCategories) => handleCategoriesChange("character", newCategories)}
      />
      <Filter
        label="Època"
        type="time_period"
        items={timePeriods}
        selectedCategories={categories.time_period}
        onSelect={(newCategories) => handleCategoriesChange("time_period", newCategories)}
      />

      {#if hasCategories}
        <Button variant="ghost" onclick={clearCategories} class="font-light">
          <Trash2Icon class="size-3.5" />
          Neteja filtres
        </Button>
      {/if}
    </div>
  </div>

  <div class="overflow-hidden rounded-md border shadow-xs mb-5">
    <Table.Root class="sm:layout-fixed">
      <Table.Header>
        {#each table.getHeaderGroups() as headerGroup (headerGroup.id)}
          <Table.Row>
            {#each headerGroup.headers as header (header.id)}
              <Table.Head
                colspan={header.colSpan}
                style={`width: ${header.getSize()}px`}
                class="h-11"
              >
                <DataTableHeader {table} {header} />
              </Table.Head>
            {/each}
            <Table.Head aria-hidden="true"></Table.Head>
          </Table.Row>
        {/each}
      </Table.Header>
      <Table.Body>
        {#if queryData.isLoading}
          <Table.Row>
            <Table.Cell colspan={columns.length} class="h-24 text-center">
              <LoaderCircleIcon class="animate-spin text-accent-foreground/30 w-full" />
            </Table.Cell>
          </Table.Row>
        {:else}
          {#each table.getRowModel().rows as row (row.id)}
            <Table.Row data-state={row.getIsSelected() && "selected"} class="relative">
              {#each row.getVisibleCells() as cell (cell.id)}
                <Table.Cell style={`width: ${cell.column.getSize()}px`}>
                  <FlexRender content={cell.column.columnDef.cell} context={cell.getContext()} />
                </Table.Cell>
              {/each}
              <Table.Cell>
                <a
                  href={`/episodis/${row.original.id}/${row.original.slug}`}
                  aria-label="Ves a l'episodi"
                  class="absolute top-0 left-0 w-full h-full outline-offset-[-2px]"
                >
                  <span class="sr-only">Ves a l'episodi {row.original.title}</span>
                </a>
              </Table.Cell>
            </Table.Row>
          {:else}
            <Table.Row>
              <Table.Cell colspan={columns.length} class="h-24 text-center">
                No s'han trobat resultats.
              </Table.Cell>
            </Table.Row>
          {/each}
        {/if}
      </Table.Body>
    </Table.Root>
  </div>
  <DataTablePagination {table} />
</div>
