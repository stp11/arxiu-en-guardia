<script lang="ts">
  import { page } from "$app/state";

  import { cn } from "lib/utils";

  const links = [
    { href: "/", label: "Inici", match: "exact" as const },
    { href: "/sobre-el-projecte", label: "Sobre l'arxiu", match: "prefix" as const },
  ];

  const isActive = (href: string, match: "exact" | "prefix") => {
    const path = page.url.pathname;
    return match === "exact" ? path === href : path.startsWith(href);
  };
</script>

<nav aria-label="Navegació principal" class="mx-auto w-full max-w-screen-2xl px-6 pt-4 md:px-10">
  <ul
    class="m-0 flex list-none items-center justify-end gap-4 p-0 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3 sm:gap-6"
  >
    {#each links as link (link.href)}
      {@const active = isActive(link.href, link.match)}
      <li>
        <a
          href={link.href}
          aria-current={active ? "page" : undefined}
          class={cn(
            "hover:text-vermillion-deep focus-visible:text-ink",
            active && "border-b border-vermillion pb-0.5 text-ink"
          )}
        >
          {link.label}
        </a>
      </li>
    {/each}
  </ul>
</nav>
