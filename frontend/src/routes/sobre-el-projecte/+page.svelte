<script lang="ts">
  import { SITE_NAME, SITE_URL } from "#lib/constants.js";

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
  <article>
    <header class="border-b-[3px] border-double border-rule pt-4 pb-7 md:pt-8 md:pb-8">
      <h1
        class="max-w-[18ch] font-serif text-[clamp(2rem,5vw,3.25rem)] font-medium text-balance leading-[1.05] tracking-[-0.015em]"
      >
        Sobre l'arxiu
      </h1>
    </header>

    <!-- Intro -->
    <section class="mt-9 max-w-[70ch]">
      <p class="font-serif text-[clamp(1.2rem,2vw,1.625rem)] leading-snug text-pretty text-ink">
        Arxiu en Guàrdia neix amb la voluntat d'organitzar i fer accessible el ric patrimoni de
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
        Encara hi ha categories que no són del tot precises i que anirem millorant amb el temps. Si
        hi detectes errors o tens propostes de millora, escriu-nos a <span class="font-bold"
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

    <!-- Viquipèdia i mapa -->
    <section class="mt-16 max-w-[70ch]">
      <h2
        class="mb-4 border-b border-rule pb-2 font-mono text-[11px] font-medium uppercase tracking-[0.16em] text-ink-3"
      >
        Viquipèdia i mapa
      </h2>
      <p class="font-serif text-lg leading-relaxed text-ink">
        Cada episodi enllaça als articles de la <a
          href="https://ca.wikipedia.org"
          target="_blank"
          rel="noopener noreferrer"
          class="text-vermillion-deep underline underline-offset-4 hover:text-ink">Viquipèdia</a
        > que tracten el mateix tema, per si vols aprofundir-hi.
      </p>
      <p class="mt-4 font-serif text-lg leading-relaxed text-ink">
        Els llocs dels episodis també es poden explorar en un <a
          href="/mapa"
          class="text-vermillion-deep underline underline-offset-4 hover:text-ink">mapa</a
        >. Les coordenades provenen també de la Viquipèdia, i el mapa base, d'<a
          href="https://www.openstreetmap.org/copyright"
          target="_blank"
          rel="noopener noreferrer"
          class="text-vermillion-deep underline underline-offset-4 hover:text-ink">OpenStreetMap</a
        >
        .
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
          >github.com/stp11/arxiu-en-guardia</a
        >.
      </p>
    </section>
  </article>
</div>
