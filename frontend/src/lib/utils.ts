import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

import type { CategoryType } from "client";

export type { WithoutChild, WithoutChildren, WithoutChildrenOrChild } from "bits-ui";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export type WithElementRef<T, U extends HTMLElement = HTMLElement> = T & { ref?: U | null };

export const capitalize = (str: string) => {
  return str.charAt(0).toUpperCase() + str.slice(1);
};

export const CATEGORY_TYPE_LABELS: Record<CategoryType, string> = {
  topic: "Temes",
  location: "Llocs",
  character: "Personatges",
  time_period: "Èpoques",
};

export const CATEGORY_TYPE_LABELS_SINGULAR: Record<CategoryType, string> = {
  topic: "Tema",
  location: "Lloc",
  character: "Personatge",
  time_period: "Època",
};

export const CATEGORY_TYPE_COLORS: Record<CategoryType, string> = {
  topic: "var(--vermillion-deep)",
  location: "var(--teal)",
  character: "var(--character)",
  time_period: "var(--plum)",
};

export const getCategoryStyles = (category: CategoryType | null) => {
  if (!category) return "";
  switch (category) {
    case "topic":
      return "text-vermillion-deep border-vermillion-deep/30";
    case "location":
      return "text-teal border-teal/30";
    case "character":
      return "text-character border-character/30";
    case "time_period":
      return "text-plum border-plum/30";
  }
};

export const getCheckboxStyles = (category: CategoryType | null) => {
  if (!category) return "";
  switch (category) {
    case "topic":
      return "data-[state=checked]:bg-vermillion-deep data-[state=checked]:border-vermillion-deep";
    case "location":
      return "data-[state=checked]:bg-teal data-[state=checked]:border-teal";
    case "character":
      return "data-[state=checked]:bg-character data-[state=checked]:border-character";
    case "time_period":
      return "data-[state=checked]:bg-plum data-[state=checked]:border-plum";
  }
};

export const hasDescription = (description: string | null | undefined) => {
  if (!description) return false;
  const trimmedDescription = description.trim();
  return trimmedDescription !== "" && trimmedDescription.toLocaleLowerCase() !== "en guàrdia";
};

export type HighlightChunk = { text: string; match: boolean };

const escapeRegExp = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export const highlightMatches = (text: string, query: string): HighlightChunk[] => {
  if (!text) return [];
  const q = query.trim();
  if (q.length < 2) return [{ text, match: false }];

  const re = new RegExp(escapeRegExp(q), "gi");
  const chunks: HighlightChunk[] = [];
  let lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > lastIndex) chunks.push({ text: text.slice(lastIndex, m.index), match: false });
    chunks.push({ text: m[0], match: true });
    lastIndex = m.index + m[0].length;
    if (m[0].length === 0) re.lastIndex++;
  }
  if (lastIndex < text.length) chunks.push({ text: text.slice(lastIndex), match: false });
  return chunks;
};

export const extractSnippet = (text: string, query: string, before = 40, after = 200): string => {
  if (!text) return "";
  const q = query.trim();
  if (q.length < 2) return text;
  const idx = text.toLowerCase().indexOf(q.toLowerCase());
  if (idx < 0) return text;
  const start = Math.max(0, idx - before);
  const end = Math.min(text.length, idx + q.length + after);
  let snippet = text.slice(start, end);
  if (start > 0) snippet = "..." + snippet;
  if (end < text.length) snippet = snippet + "...";
  return snippet;
};
