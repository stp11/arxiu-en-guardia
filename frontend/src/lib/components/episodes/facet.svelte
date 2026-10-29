<script lang="ts">
  import type { CategoryType } from "#client";
  import { CATEGORY_TYPE_COLORS, cn } from "#lib/utils.js";
  import { Check, ChevronDown } from "@lucide/svelte";
  import { Popover } from "bits-ui";

  import CategoryChip from "./category-chip.svelte";

  type FacetItem = { slug: string; name: string; count: number };

  type FacetProps = {
    label: string;
    type: CategoryType;
    items: FacetItem[];
    selected: string[];
    onToggle: (slug: string) => void;
    // Whether an episode needs every selected item rather than any of them.
    matchAll: boolean;
    onMatchAllChange: (matchAll: boolean) => void;
    placeholder?: string;
    loading?: boolean;
    // Per slug, its episodes under the search and the other facets'
    // filters, and this one's with matchAll; without it, each item's own
    // count. A slug missing from it has none.
    counts?: Map<string, number>;
  };

  let {
    label,
    type,
    items,
    selected,
    onToggle,
    matchAll,
    onMatchAllChange,
    placeholder,
    loading = false,
    counts,
  }: FacetProps = $props();

  const countOf = (item: FacetItem) => (counts ? (counts.get(item.slug) ?? 0) : item.count);

  let open = $state(false);
  let query = $state("");

  const swatch = $derived(CATEGORY_TYPE_COLORS[type]);
  const selectedSet = $derived(new Set(selected));
  const itemsBySlug = $derived(new Map(items.map((i) => [i.slug, i])));
  const selectedItems = $derived(
    selected.map((slug) => itemsBySlug.get(slug)).filter((i) => i !== undefined)
  );

  // Dead ends are left out, but not the selected ones, so they can be
  // unticked.
  const available = $derived(
    counts ? items.filter((i) => countOf(i) > 0 || selectedSet.has(i.slug)) : items
  );

  const options = $derived.by(() => {
    const q = query.trim().toLowerCase();
    return q ? available.filter((i) => i.name.toLowerCase().includes(q)) : available;
  });

  // With fewer than two to pick from there's nothing to combine, but with
  // matchAll it stays, as it's the way back to the wider list.
  const canCombine = $derived(available.length > 1 || matchAll);

  const onOpenChange = (next: boolean) => {
    if (!next) query = "";
  };

  const modes = [
    { matchAll: false, label: "Inclou una de les categories" },
    { matchAll: true, label: "Inclou totes les categories" },
  ];
</script>

<div class="mb-4">
  <Popover.Root bind:open {onOpenChange}>
    <Popover.Trigger
      class={cn(
        "flex w-full cursor-pointer items-baseline justify-between border-b border-rule py-1.5 text-left select-none",
        "hover:border-ink-3 focus-visible:border-ink-3 focus-visible:outline-none data-[state=open]:border-vermillion"
      )}
    >
      <h3 class="font-serif text-[17px] font-semibold tracking-[0.01em]">{label}</h3>
      <span class="flex items-center gap-2 font-mono text-[11px] text-ink-3">
        {#if selected.length > 0}
          <span class="text-vermillion-deep">{selected.length}</span>
        {/if}
        <ChevronDown class={cn("size-3 transition-transform", open && "rotate-180")} />
      </span>
    </Popover.Trigger>

    <Popover.Portal>
      <Popover.Content
        align="start"
        sideOffset={4}
        class="z-[60] w-[max(var(--bits-popover-anchor-width),16rem)] rounded-sm border border-rule bg-paper p-2 text-ink shadow-lg"
      >
        <input
          id={`facet-search-${type}`}
          type="search"
          bind:value={query}
          {placeholder}
          aria-label={placeholder ?? `Cerca ${label.toLowerCase()}`}
          class={cn(
            "mb-2 w-full rounded-sm border border-rule bg-paper-2 px-2 py-1.5 text-[15px] md:text-[13px] text-ink outline-none placeholder:italic placeholder:text-ink-3 focus:border-vermillion",
            "facet-search-clear"
          )}
        />

        {#if canCombine}
          <div
            role="radiogroup"
            aria-label="Com es combinen les categories"
            class="mb-2 flex flex-col border-b border-rule pb-1.5 text-[13px]"
          >
            {#each modes as mode (mode.label)}
              {@const checked = matchAll === mode.matchAll}
              <button
                type="button"
                role="radio"
                aria-checked={checked}
                onclick={() => onMatchAllChange(mode.matchAll)}
                class={cn(
                  "flex cursor-pointer items-center gap-2 rounded-sm px-1.5 py-1 text-left text-ink-3 hover:bg-black/5 hover:text-ink",
                  checked && "text-ink"
                )}
              >
                <span
                  class="flex size-3.5 flex-none items-center justify-center rounded-full border border-ink-3"
                >
                  {#if checked}<span class="size-1.5 rounded-full bg-ink"></span>{/if}
                </span>
                {mode.label}
              </button>
            {/each}
          </div>
        {/if}

        {#if loading && items.length === 0}
          <p class="px-1 py-1.5 text-xs italic text-ink-3">Carregant…</p>
        {:else if options.length === 0}
          <p class="px-1 py-1.5 text-xs italic text-ink-3">Cap resultat</p>
        {:else}
          <ul
            class="m-0 flex max-h-80 list-none flex-col gap-0.5 overflow-y-auto overscroll-contain p-0"
          >
            {#each options as item (item.slug)}
              {@const active = selectedSet.has(item.slug)}
              <li>
                <button
                  type="button"
                  aria-pressed={active}
                  onclick={() => onToggle(item.slug)}
                  class={cn(
                    "flex w-full cursor-pointer items-center justify-between gap-2 rounded-sm px-1.5 py-1 text-[14px] text-ink-2 transition-colors",
                    "hover:bg-black/5 hover:text-ink",
                    active && "text-ink"
                  )}
                >
                  <span class="flex min-w-0 items-center gap-2 text-left">
                    <span
                      class="flex size-3.5 flex-none items-center justify-center rounded-sm border border-rule"
                      style:background={active ? swatch : "transparent"}
                      style:border-color={active ? swatch : undefined}
                    >
                      {#if active}<Check class="size-2.5 text-paper" strokeWidth={3} />{/if}
                    </span>
                    <span class="line-clamp-1">{item.name}</span>
                  </span>
                  <span
                    class={cn("font-mono text-[10px] text-ink-3", active && "text-vermillion-deep")}
                    >{countOf(item)}</span
                  >
                </button>
              </li>
            {/each}
          </ul>
        {/if}
      </Popover.Content>
    </Popover.Portal>
  </Popover.Root>

  {#if selectedItems.length > 1}
    <p class="mt-1.5 mb-0 px-0.5 text-[13px] italic text-ink-3">
      {matchAll
        ? `Episodis amb ${selectedItems.length === 2 ? "les dues" : "totes les"} categories`
        : "Episodis amb una de les categories"}
    </p>
  {/if}
  {#if selectedItems.length > 0}
    <ul class="m-0 mt-2 flex list-none flex-wrap gap-1.5 p-0">
      {#each selectedItems as item (item.slug)}
        <li class="max-w-full">
          <CategoryChip
            {type}
            name={item.name}
            active
            removable
            onclick={() => onToggle(item.slug)}
          />
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  input[type="search"].facet-search-clear::-webkit-search-cancel-button {
    width: 0.75rem;
    height: 0.75rem;
  }
</style>
