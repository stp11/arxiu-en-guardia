<script lang="ts">
  import { ArrowLeft } from "@lucide/svelte";

  import type { CategoryType } from "client";

  import { CATEGORY_TYPE_LABELS_SINGULAR, cn, hasDescription } from "lib/utils";

  const { data } = $props();

  const fmtLong = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString("ca", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  };

  const groupedCategories = $derived.by(() => {
    if (!data.episode?.categories)
      return {} as Record<CategoryType, typeof data.episode.categories>;
    const out = {
      time_period: [] as typeof data.episode.categories,
      location: [] as typeof data.episode.categories,
      character: [] as typeof data.episode.categories,
      topic: [] as typeof data.episode.categories,
    };
    for (const c of data.episode.categories) {
      if (c.type) out[c.type].push(c);
    }
    return out;
  });

  const orderedTypes: CategoryType[] = ["time_period", "location", "character", "topic"];
</script>

{#if data.episode}
  {@const episode = data.episode}

  <div class="mx-auto w-full max-w-[1100px] px-6 pt-8 pb-12 md:px-10 md:pt-14">
    <!-- Mini masthead bar -->
    <div
      class="flex items-center justify-between gap-4 border-b-[3px] border-double border-rule pt-5 pb-4"
    >
      <a
        href="/"
        class="inline-block font-serif leading-[0.95] tracking-[-0.005em] text-ink"
        aria-label="Arxiu En Guàrdia"
      >
        <span class="block text-[15px] font-medium md:text-base">Arxiu</span>
        <span class="block text-xl font-medium italic text-vermillion-deep md:text-2xl">
          En&nbsp;Guàrdia
        </span>
      </a>
      <a
        href="/"
        class="inline-flex items-center gap-2 rounded-sm border border-rule bg-white/30 px-3 py-2 font-mono text-[11px] uppercase tracking-[0.1em] text-ink-2 transition-colors hover:border-ink hover:bg-ink hover:text-paper"
      >
        <ArrowLeft class="size-3.5" />
        Torna a l'arxiu
      </a>
    </div>

    <article>
      <!-- Episode head -->
      <header class="border-b border-rule py-12 md:py-14">
        {#if episode.published_at}
          <time
            datetime={episode.published_at}
            class="mb-5 block font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-vermillion-deep"
          >
            {fmtLong(episode.published_at)}
          </time>
        {/if}

        <h1
          class="max-w-[18ch] font-serif text-[clamp(2.25rem,5.5vw,4.25rem)] font-medium text-balance leading-[1.05] tracking-[-0.015em]"
        >
          {episode.title}
        </h1>
      </header>

      <!-- Player -->
      <div class="mt-9">
        <div
          class="border border-rule bg-[#1a1410] p-3.5 shadow-[0_24px_60px_-30px_rgba(31,26,20,0.5)]"
        >
          <div class="relative aspect-video w-full overflow-hidden bg-black">
            <iframe
              title={`Episodi ${episode.id} — ${episode.title}`}
              src={`https://www.3cat.cat/3cat/audio/${episode.id}/embed/`}
              allowfullscreen
              scrolling="no"
              class="absolute inset-0 size-full border-0"
            ></iframe>
          </div>
        </div>
        <div
          class="mt-2.5 flex flex-wrap items-center justify-between gap-2 font-mono text-[10px] uppercase tracking-[0.12em] text-ink-3"
        >
          <span>Font · 3Cat</span>
          <a
            href={`https://www.3cat.cat/3cat/${episode.slug}}/audio/${episode.id}/`}
            target="_blank"
            rel="noopener noreferrer"
            class="text-vermillion-deep hover:text-ink"
          >
            Ves a la pàgina oficial ↗
          </a>
        </div>
      </div>

      <!-- Body grid: description + sidebar -->
      <div class="mt-14 grid grid-cols-1 gap-12 md:grid-cols-[1fr_280px] md:gap-16">
        <!-- Description -->
        {#if hasDescription(episode.description)}
          <section>
            <h2
              class="mb-4 border-b border-rule pb-2 font-mono text-[11px] font-medium uppercase tracking-[0.16em] text-ink-3"
            >
              Descripció
            </h2>
            <p
              class="font-serif text-[clamp(1.2rem,2vw,1.625rem)] leading-snug text-pretty text-ink first-letter:float-left first-letter:mt-2 first-letter:mr-2.5 first-letter:font-serif first-letter:text-[76px] first-letter:font-semibold first-letter:leading-[0.85] first-letter:text-vermillion-deep"
            >
              {episode.description}
            </p>
          </section>
        {:else}
          <section>
            <h2
              class="mb-4 border-b border-rule pb-2 font-mono text-[11px] font-medium uppercase tracking-[0.16em] text-ink-3"
            >
              Descripció
            </h2>
            <p class="font-serif text-xl text-ink-3 italic">Sense descripció</p>
          </section>
        {/if}

        <!-- Sidebar: categories grouped by type -->
        <aside class="flex flex-col gap-9 self-start md:sticky md:top-6">
          {#if episode.categories && episode.categories.length > 0}
            <section>
              <h2
                class="mb-4 border-b border-rule pb-2 font-mono text-[11px] font-medium uppercase tracking-[0.16em] text-ink-3"
              >
                Categories
              </h2>

              {#each orderedTypes as type (type)}
                {@const group = groupedCategories[type] ?? []}
                {#if group.length > 0}
                  <div class="mb-4 last:mb-0">
                    <span
                      class="mb-2 block font-mono text-[9px] uppercase tracking-[0.16em] text-ink-3"
                    >
                      {CATEGORY_TYPE_LABELS_SINGULAR[type]}
                    </span>
                    <div class="flex flex-wrap gap-1.5">
                      {#each group as c (c.id)}
                        <span
                          class={cn(
                            "inline-flex items-center gap-1.5 rounded-sm border bg-white/40 px-2.5 py-1 font-mono text-[11px] leading-snug uppercase tracking-[0.05em] whitespace-nowrap transition-transform hover:-translate-y-[1px]",
                            {
                              "border-vermillion-deep/30 text-vermillion-deep": type === "topic",
                              "border-teal/30 text-teal": type === "location",
                              "border-character/30 text-character": type === "character",
                              "border-plum/30 text-plum": type === "time_period",
                            }
                          )}
                        >
                          <span class="size-1.5 rounded-full" style:background="currentColor"
                          ></span>
                          {c.name}
                        </span>
                      {/each}
                    </div>
                  </div>
                {/if}
              {/each}
            </section>
          {/if}

          {#if episode.published_at}
            <section>
              <h2
                class="mb-4 border-b border-rule pb-2 font-mono text-[11px] font-medium uppercase tracking-[0.16em] text-ink-3"
              >
                Catalogat
              </h2>
              <div class="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-2">
                {fmtLong(episode.published_at)}
              </div>
            </section>
          {/if}
        </aside>
      </div>
    </article>
  </div>
{/if}
