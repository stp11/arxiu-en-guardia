import { createRawSnippet } from "svelte";

import { renderSnippet } from "$lib/components/ui/data-table/render-helpers.js";
import { AudioLinesIcon, CalendarIcon, TagsIcon, TextAlignJustifyIcon } from "@lucide/svelte";
import type { ColumnDef } from "@tanstack/table-core";

import type { EpisodeWithCategories } from "client";

import { capitalize, getCategoryStyles } from "lib/utils";

export const columns: ColumnDef<EpisodeWithCategories>[] = [
  {
    accessorKey: "title",
    header: "Títol",
    enableSorting: false,
    cell: ({ row }) => {
      const titleCellSnippet = createRawSnippet(() => ({
        render: () => `<div class="font-normal">${row.original.title}</div>`,
      }));
      return renderSnippet(titleCellSnippet, row.original.title);
    },
    meta: {
      icon: AudioLinesIcon,
    },
  },
  {
    accessorKey: "description",
    header: "Descripció",
    size: 768,
    enableSorting: false,
    cell: ({ row }) => {
      const descriptionRow = row.original.description;
      const description =
        descriptionRow?.toLocaleLowerCase() === "en guàrdia" || descriptionRow?.trim() === ""
          ? "Sense descripció"
          : descriptionRow;
      const descriptionCellSnippet = createRawSnippet(() => ({
        render: () => `<div class="line-clamp-3">${description}</div>`,
      }));
      return renderSnippet(descriptionCellSnippet, description);
    },
    meta: {
      icon: TextAlignJustifyIcon,
    },
  },
  {
    accessorKey: "categories",
    header: "Categories",
    size: 350,
    enableSorting: false,
    cell: ({ row }) => {
      const categoriesCellSnippet = createRawSnippet(() => ({
        render: () =>
          `<div class="flex flex-wrap gap-2">
          ${row.original.categories?.map((category) => `<span class="text-xs rounded-md px-2 py-0.5 ${getCategoryStyles(category.type)}">${capitalize(category.name)}</span>`).join("")}
        </div>`,
      }));
      return renderSnippet(categoriesCellSnippet, row.original.categories);
    },
    meta: {
      icon: TagsIcon,
    },
  },
  {
    accessorKey: "published_at",
    header: "Data de publicació",
    size: 150,
    enableSorting: true,
    cell: ({ row }) => {
      if (!row.original.published_at) return null;
      const date = new Intl.DateTimeFormat("ca", {
        year: "numeric",
        month: "short",
        day: "numeric",
      }).format(new Date(row.original.published_at));

      const publishedAtCellSnippet = createRawSnippet(() => ({
        render: () => `<div class="pr-3 text-right">${date}</div>`,
      }));
      return renderSnippet(publishedAtCellSnippet, date);
    },
    meta: {
      icon: CalendarIcon,
    },
  },
];
