<script lang="ts">
  import { ChevronDown } from "@lucide/svelte";

  import type { CategoryType } from "client";

  import { CATEGORY_TYPE_COLORS, cn } from "lib/utils";

  type FacetItem = { id: number; name: string; count: number };

  type FacetProps = {
    label: string;
    type: CategoryType;
    items: FacetItem[];
    selected: number[];
    onToggle: (id: number) => void;
    cap?: number;
    placeholder?: string;
    showSearch?: boolean;
    loading?: boolean;
  };

  let {
    label,
    type,
    items,
    selected,
    onToggle,
    cap = 8,
    showSearch = true,
    placeholder,
    loading = false,
  }: FacetProps = $props();

  let collapsed = $state(false);
  let expanded = $state(false);
  let query = $state("");

  const swatch = $derived(CATEGORY_TYPE_COLORS[type]);
  const clearClass = $derived(`search-clear-${type.replace(/_/g, "-")}`);
  const selectedSet = $derived(new Set(selected));
  const itemsById = $derived(new Map(items.map((i) => [i.id, i])));

  const filtered = $derived.by(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((i) => i.name.toLowerCase().includes(q));
  });

  const visible = $derived.by(() => {
    const showAll = !!query.trim() || expanded;
    if (showAll) return filtered;
    const head = filtered.slice(0, cap);
    const headIds = new Set(head.map((i) => i.id));
    const tail: typeof items = [];
    for (const id of selected) {
      const item = itemsById.get(id);
      if (item && !headIds.has(id)) tail.push(item);
    }
    return tail.length ? [...head, ...tail] : head;
  });

  const hidden = $derived(filtered.length - visible.length);
  const moreLabel = $derived(
    hidden > 0
      ? `Mostra'n ${hidden} més`
      : expanded && filtered.length > cap
        ? "Mostra'n menys"
        : ""
  );
</script>

<div class="mb-6">
  <button
    type="button"
    onclick={() => (collapsed = !collapsed)}
    class="mb-2 flex w-full cursor-pointer items-baseline justify-between border-b border-rule pb-1.5 text-left select-none"
  >
    <h3 class="font-serif text-[17px] font-semibold tracking-[0.01em]">{label}</h3>
    <span
      class={cn("font-mono text-[11px] text-ink-3 transition-transform", collapsed && "-rotate-90")}
      aria-hidden="true"><ChevronDown class="size-3" /></span
    >
  </button>

  {#if !collapsed}
    {#if showSearch}
      <input
        id={`facet-search-${type}`}
        type="search"
        bind:value={query}
        {placeholder}
        aria-label={placeholder ?? `Cerca ${label.toLowerCase()}`}
        class={cn(
          "mb-2 w-full rounded-sm border border-rule bg-paper-2 px-2 py-1.5 text-[13px] text-ink outline-none placeholder:italic placeholder:text-ink-3 focus:border-vermillion",
          clearClass
        )}
      />
    {/if}

    {#if loading && items.length === 0}
      <ul
        class="m-0 flex list-none flex-col gap-1 p-0"
        aria-busy="true"
        aria-label={`Carregant ${label.toLowerCase()}`}
      >
        {#each Array.from({ length: cap }) as _, i (i)}
          <li class="animate-pulse">
            <div class="flex items-center justify-between px-1.5 py-1">
              <span class="flex items-center gap-2">
                <span class="size-2 flex-none rounded-full bg-paper-edge/80"></span>
                <span
                  class="block h-3.5 rounded-sm bg-paper-edge"
                  style="width: {6 + ((i * 1.3) % 5)}rem"
                ></span>
              </span>
              <span class="block h-2.5 w-3 rounded-sm bg-paper-edge/70"></span>
            </div>
          </li>
        {/each}
      </ul>
    {:else if visible.length === 0}
      <p class="px-1 py-1.5 text-xs italic text-ink-3">Cap resultat</p>
    {:else}
      <ul class="m-0 flex list-none flex-col gap-1 p-0">
        {#each visible as item (item.id)}
          {@const active = selectedSet.has(item.id)}
          <li>
            <button
              type="button"
              aria-pressed={active}
              onclick={() => onToggle(item.id)}
              class={cn(
                "group flex w-full cursor-pointer items-center justify-between rounded-sm px-1.5 py-1 text-[14px] text-ink-2 transition-colors",
                "hover:bg-black/5 hover:text-ink",
                active && "bg-vermillion/10 text-ink"
              )}
            >
              <span class="flex items-center gap-2 text-left">
                <span
                  class="size-2 flex-none rounded-full"
                  style:background={swatch}
                  style:box-shadow={active ? `0 0 0 2px var(--paper), 0 0 0 3px ${swatch}` : "none"}
                ></span>
                <span class="line-clamp-1">{item.name}</span>
              </span>
              <span class={cn("font-mono text-[10px] text-ink-3", active && "text-vermillion-deep")}
                >{item.count}</span
              >
            </button>
          </li>
        {/each}
      </ul>
    {/if}

    {#if moreLabel && !query.trim()}
      <button
        type="button"
        onclick={() => (expanded = !expanded)}
        class="mt-1 cursor-pointer px-1 py-1.5 text-left font-mono text-[10px] uppercase tracking-[0.1em] text-vermillion-deep hover:text-ink"
      >
        {moreLabel}
      </button>
    {/if}
  {/if}
</div>

<style>
  :global(input[type="search"].search-clear-topic::-webkit-search-cancel-button) {
    width: 0.75rem;
    height: 0.75rem;
    background-image: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%23c93f1b%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22M18%206%206%2018%22%2F%3E%3Cpath%20d%3D%22m6%206%2012%2012%22%2F%3E%3C%2Fsvg%3E");
  }

  :global(input[type="search"].search-clear-location::-webkit-search-cancel-button) {
    width: 0.75rem;
    height: 0.75rem;
    background-image: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%232e5e58%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22M18%206%206%2018%22%2F%3E%3Cpath%20d%3D%22m6%206%2012%2012%22%2F%3E%3C%2Fsvg%3E");
  }

  :global(input[type="search"].search-clear-character::-webkit-search-cancel-button) {
    width: 0.75rem;
    height: 0.75rem;
    background-image: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%23a25c12%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22M18%206%206%2018%22%2F%3E%3Cpath%20d%3D%22m6%206%2012%2012%22%2F%3E%3C%2Fsvg%3E");
  }

  :global(input[type="search"].search-clear-time-period::-webkit-search-cancel-button) {
    width: 0.75rem;
    height: 0.75rem;
    background-image: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%235b3a4a%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22M18%206%206%2018%22%2F%3E%3Cpath%20d%3D%22m6%206%2012%2012%22%2F%3E%3C%2Fsvg%3E");
  }
</style>
