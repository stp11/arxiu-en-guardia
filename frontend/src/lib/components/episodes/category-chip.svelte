<script lang="ts">
  import { cn } from "#lib/utils.js";
  import { XIcon } from "@lucide/svelte";

  type CategoryChipProps = {
    type: string | null;
    name: string;
    // Ticked in the filters: filled with its type's colour.
    active?: boolean;
    // With an ×, for a chip whose click takes the filter off.
    removable?: boolean;
    onclick: () => void;
  };

  let { type, name, active = false, removable = false, onclick }: CategoryChipProps = $props();
</script>

<button
  type="button"
  aria-pressed={removable ? undefined : active}
  aria-label={removable ? `Treu ${name}` : undefined}
  {onclick}
  class={cn(
    "inline-flex max-w-full cursor-pointer items-center gap-1.5 rounded-sm border bg-paper-2 px-2 py-0.5 font-mono text-[10px] leading-snug uppercase tracking-[0.05em] whitespace-nowrap transition-transform hover:-translate-y-[1px]",
    {
      "border-vermillion-deep/30 text-vermillion-deep": type === "topic",
      "border-teal/30 text-teal": type === "location",
      "border-character/30 text-character": type === "character",
      "border-plum/30 text-plum": type === "time_period",
    },
    active && "border-transparent text-paper",
    active && {
      "bg-vermillion-deep": type === "topic",
      "bg-teal": type === "location",
      "bg-character": type === "character",
      "bg-plum": type === "time_period",
    }
  )}
>
  <span class="size-1.5 flex-none rounded-full" style:background="currentColor" style:opacity="0.9"
  ></span>
  <span class="truncate">{name}</span>
  {#if removable}
    <XIcon class="-mr-0.5 size-2.5 flex-none opacity-80" strokeWidth={3} />
  {/if}
</button>
