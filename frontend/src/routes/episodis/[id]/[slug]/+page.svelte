<script lang="ts">
  import { ArrowLeft } from "@lucide/svelte";

  import { capitalize, getCategoryStyles, hasDescription } from "lib/utils";

  const { data } = $props();

  const mockRelatedEpisodes = [
    {
      id: 1263950,
      slug: "el-mite-del-bushido",
      title: 'El mite del "bushido"',
      published_at: "2025-12-13T15:00:00",
      image_url: "https://img.3cat.cat/multimedia/jpg/0/2/1765284933520.jpg",
      categories: [
        { id: 1, name: "samurais", type: "topic" as const },
        { id: 2, name: "Japó", type: "location" as const },
      ],
    },
    {
      id: 1264742,
      slug: "el-periode-iberic-classic-a-catalunya",
      title: "El període ibèric clàssic a Catalunya",
      published_at: "2025-12-21T06:00:00",
      image_url: "https://img.3cat.cat/multimedia/jpg/3/2/1765886444323.jpg",
      categories: [
        { id: 3, name: "ibers", type: "topic" as const },
        { id: 4, name: "segle V aC", type: "time_period" as const },
      ],
    },
    {
      id: 1265572,
      slug: "lexecucio-de-joan-baptista-peset",
      title: "L'execució de Joan Baptista Peset",
      published_at: "2025-12-27T15:00:00",
      image_url: "https://img.3cat.cat/multimedia/jpg/6/6/1766493023666.jpg",
      categories: [
        { id: 5, name: "Joan Baptista Peset", type: "character" as const },
        { id: 6, name: "franquisme", type: "topic" as const },
      ],
    },
  ];
</script>

{#if data.episode}
  {@const episode = data.episode}

  <div class="container mx-auto max-w-4xl">
    <article class="mx-auto max-w-2xl">
      <nav class="mb-8 sm:mb-10">
        <a href="/" class="group inline-flex items-center gap-1.5 text-sm text-primary-orange">
          <ArrowLeft class="transition-transform group-hover:-translate-x-0.5 size-4" />
          Tornar al llistat
        </a>
      </nav>

      <header class="mb-10 space-y-5 sm:mb-14">
        {#if episode.published_at}
          <time
            datetime={episode.published_at}
            class="block text-xs font-medium uppercase tracking-[0.14em] text-gray-500"
          >
            {new Date(episode.published_at).toLocaleDateString("ca-ES", {
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </time>
        {/if}

        <h1
          class="text-pretty font-spline-sans text-2xl leading-[1.15] tracking-tight md:text-4xl lg:text-5xl"
        >
          {episode.title}
        </h1>

        {#if episode.categories && episode.categories.length > 0}
          <div class="flex flex-wrap gap-1.5 pt-1">
            {#each episode.categories as category (category.id)}
              <span class="rounded-md px-2 py-0.5 text-xs {getCategoryStyles(category.type)}">
                {capitalize(category.name)}
              </span>
            {/each}
          </div>
        {/if}
      </header>

      <div class="mb-12 sm:mb-16">
        <div
          class="aspect-video overflow-hidden rounded-xl bg-black shadow-lg shadow-black/5 ring-1 ring-black/5"
        >
          <iframe
            title={`audio ${episode.id}`}
            src={`https://www.3cat.cat/3cat/audio/${episode.id}/embed/`}
            allowfullscreen
            scrolling="no"
            class="h-full w-full"
          ></iframe>
        </div>
      </div>

      <section class="pb-4">
        <p class="text-lg leading-[1.75] text-gray-700">
          {#if hasDescription(episode.description)}
            {episode.description}
          {:else}
            Sense descripció
          {/if}
        </p>
      </section>
    </article>

    <!-- TODO remove hidden once implemented -->
    <aside class="mt-14 border-t border-gray-200 pt-12 sm:mt-20 sm:pt-16 hidden">
      <h2 class="mb-6 font-spline-sans text-xl tracking-tight sm:mb-8 md:text-2xl">
        Episodis relacionats
      </h2>

      <ul class="grid grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] gap-4 sm:gap-5">
        {#each mockRelatedEpisodes as related (related.id)}
          <li>
            <a
              href={`/episodis/${related.id}/${related.slug}`}
              class="group flex h-full flex-col overflow-hidden rounded-lg border border-gray-200 bg-white transition-colors hover:border-gray-300"
            >
              <div class="aspect-video overflow-hidden bg-gray-100">
                {#if related.image_url}
                  <img
                    src={related.image_url}
                    alt=""
                    loading="lazy"
                    class="h-full w-full object-cover"
                  />
                {/if}
              </div>
              <div class="flex flex-1 flex-col gap-1.5 p-4">
                <time
                  datetime={related.published_at}
                  class="text-xs font-medium uppercase tracking-[0.14em] text-gray-500"
                >
                  {new Date(related.published_at).toLocaleDateString("ca-ES", {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}
                </time>
                <h3
                  class="line-clamp-2 font-spline-sans text-base leading-snug text-gray-900 transition-colors group-hover:text-primary-orange"
                >
                  {related.title}
                </h3>
                <div class="mt-auto flex flex-wrap gap-1.5 pt-2">
                  {#each related.categories as cat (cat.id)}
                    <span class="rounded-md px-2 py-0.5 text-xs {getCategoryStyles(cat.type)}">
                      {capitalize(cat.name)}
                    </span>
                  {/each}
                </div>
              </div>
            </a>
          </li>
        {/each}
      </ul>
    </aside>
  </div>
{/if}
