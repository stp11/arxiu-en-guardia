<script lang="ts">
  import { ArrowLeft } from "@lucide/svelte";
  import { SITE_NAME, SITE_URL } from "src/lib/constants";

  import AppLogo from "lib/components/app-logo.svelte";

  const title = `Sobre l'arxiu · ${SITE_NAME}`;
  const description =
    "Iniciativa feta per oients per organitzar i fer accessibles els més de mil episodis d'En Guàrdia, el programa d'història de Catalunya Ràdio.";
  const url = `${SITE_URL}/sobre-el-projecte`;
</script>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={description} />
  <link rel="canonical" href={url} />
  <meta property="og:type" content="article" />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
  <meta property="og:url" content={url} />
  <meta name="twitter:title" content={title} />
  <meta name="twitter:description" content={description} />
</svelte:head>

<div class="mx-auto w-full max-w-[1100px] px-6 pt-8 pb-12 md:px-10 md:pt-14">
  <!-- Mini masthead bar -->
  <div
    class="flex items-center justify-between gap-4 border-b-[3px] border-double border-rule pt-5 pb-4"
  >
    <AppLogo />
    <a
      href="/"
      class="inline-flex items-center gap-2 rounded-sm border border-ink bg-ink px-3 py-2 font-mono text-[11px] uppercase tracking-[0.1em] text-paper transition-colors hover:border-vermillion-deep hover:bg-vermillion-deep"
    >
      <ArrowLeft class="size-3.5" />
      Torna a l'arxiu
    </a>
  </div>

  <article>
    <header class="border-b border-rule py-12 md:py-14">
      <span
        class="mb-5 block font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-vermillion-deep"
      >
        Sobre el projecte
      </span>
      <h1
        class="max-w-[18ch] font-serif text-[clamp(2.25rem,5.5vw,4.25rem)] font-medium text-balance leading-[1.05] tracking-[-0.015em]"
      >
        Sobre l'arxiu
      </h1>
    </header>

    <!-- Intro -->
    <section class="mt-12 max-w-[70ch]">
      <p
        class="font-serif text-[clamp(1.2rem,2vw,1.625rem)] leading-snug text-pretty text-ink first-letter:float-left first-letter:mt-2 first-letter:mr-2.5 first-letter:font-serif first-letter:text-[76px] first-letter:font-semibold first-letter:leading-[0.85] first-letter:text-vermillion-deep"
      >
        Arxiu en Guàrdia, neix amb la voluntat d'organitzar i fer accessible el ric patrimoni de
        batalles, aventures i heroïcitats que s'han narrat al programa En Guàrdia de Catalunya Ràdio
        al llarg dels anys.
      </p>

      <p class="mt-6 font-serif text-lg leading-relaxed">
        No es tracta d'un arxiu oficial del programa: és una iniciativa feta per oients per
        facilitar la descoberta i la navegació de més d'un miler d'episodis. La classificació per
        temes, personatges, èpoques i llocs s'ha fet combinant intel·ligència artificial amb una
        feina manual de supervisió i esmena.
      </p>

      <p class="mt-4 font-serif text-lg leading-relaxed">
        Encara hi ha categories que no són del tot acurades i que anirem millorant amb el temps. Si
        hi detectes errors o tens propostes, no dubtis a contactar-nos.
      </p>
    </section>

    <!-- Codi obert -->
    <section class="mt-16 max-w-[70ch]">
      <h2
        class="mb-4 border-b border-rule pb-2 font-mono text-[11px] font-medium uppercase tracking-[0.16em] text-ink-3"
      >
        Codi obert
      </h2>
      <p class="font-serif text-lg leading-relaxed text-ink">
        El projecte és de codi obert i està publicat sota la <a
          href="https://github.com/stp11/arxiu-en-guardia/blob/main/LICENCE.txt"
          target="_blank"
          rel="noopener noreferrer"
          class="text-vermillion-deep underline underline-offset-4 hover:text-ink">llicència MIT</a
        >. Pots consultar el codi, obrir <em>issues</em> o contribuir-hi a
        <a
          href="https://github.com/stp11/arxiu-en-guardia"
          target="_blank"
          rel="noopener noreferrer"
          class="text-vermillion-deep underline underline-offset-4 hover:text-ink"
          >github.com/stp11/en-guardia</a
        >.
      </p>
    </section>

    <!-- Contacte -->
    <section id="contacte" class="mt-16 max-w-[70ch] scroll-mt-20">
      <h2
        class="mb-4 border-b border-rule pb-2 font-mono text-[11px] font-medium uppercase tracking-[0.16em] text-ink-3"
      >
        Contacte
      </h2>
      <p class="font-serif text-lg leading-relaxed text-ink">
        Si tens suggeriments, correccions o vols saludar, escriu-nos a <span class="font-bold"
          >info@arxiu-en-guardia.com</span
        >.
      </p>
      <p class="mt-4 font-serif text-lg leading-relaxed text-ink">
        Si el projecte et resulta útil i vols donar-hi suport, pots convidar-nos a un cafè a <a
          href="https://buymeacoffee.com/arxiuenguardia"
          target="_blank"
          rel="noopener noreferrer"
          class="text-vermillion-deep underline underline-offset-4 hover:text-ink"
          >Buy Me a Coffee</a
        >.
      </p>
    </section>
  </article>
</div>
