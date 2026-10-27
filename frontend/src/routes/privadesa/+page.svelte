<script lang="ts">
  import { SITE_NAME, SITE_URL } from "#lib/constants.js";

  const title = `Privadesa · ${SITE_NAME}`;
  const description =
    "Quines dades es tracten quan visites l'arxiu: sense comptes ni galetes pròpies, només estadístiques agregades i els registres tècnics de l'allotjament.";
  const url = `${SITE_URL}/privadesa`;

  const linkClass = "text-vermillion-deep underline underline-offset-4 hover:text-ink";
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
        Política de privadesa
      </h1>
    </header>

    <!-- Intro -->
    <section class="mt-9 max-w-[70ch]">
      <p class="font-serif text-[clamp(1.2rem,2vw,1.625rem)] leading-snug text-pretty text-ink">
        Aquest web no recull dades personals. No té formularis, comptes, galetes pròpies ni sistemes
        d'analítica que t'identifiquin.
      </p>
    </section>

    <!-- Preferències -->
    <section class="mt-16 max-w-[70ch]">
      <h2
        class="mb-4 border-b border-rule pb-2 font-mono text-[11px] font-medium uppercase tracking-[0.16em] text-ink-3"
      >
        Preferències del navegador
      </h2>
      <p class="font-serif text-lg leading-relaxed text-ink">
        El web només desa al teu dispositiu si prefereixes el mode clar o el fosc, i quins avisos de
        novetats has tancat. Aquesta informació es guarda a l'emmagatzematge local del navegador.
      </p>
    </section>

    <!-- Estadístiques -->
    <section class="mt-16 max-w-[70ch]">
      <h2
        class="mb-4 border-b border-rule pb-2 font-mono text-[11px] font-medium uppercase tracking-[0.16em] text-ink-3"
      >
        Estadístiques de visites
      </h2>
      <p class="font-serif text-lg leading-relaxed text-ink">
        Fem servir Cloudflare Web Analytics per saber quantes visites rep el web i quines pàgines es
        consulten més. Aquesta eina no utilitza galetes ni crea perfils dels visitants: només en
        veiem xifres agregades. Pots consultar la <a
          href="https://www.cloudflare.com/privacypolicy/"
          target="_blank"
          rel="noopener noreferrer"
          class={linkClass}>política de privadesa de Cloudflare</a
        >.
      </p>
    </section>

    <!-- Allotjament -->
    <section class="mt-16 max-w-[70ch]">
      <h2
        class="mb-4 border-b border-rule pb-2 font-mono text-[11px] font-medium uppercase tracking-[0.16em] text-ink-3"
      >
        Allotjament i registres
      </h2>
      <p class="font-serif text-lg leading-relaxed text-ink">
        El web es distribueix a través de Cloudflare, que tracta dades tècniques de cada petició
        (com ara l'adreça IP o el navegador) per servir les pàgines i protegir-les d'abusos, d'acord
        amb la seva política de privadesa. La base de dades i l'API de l'arxiu estan allotjades en
        un servidor d'un proveïdor extern. Aquest servidor no guarda cap registre de les visites.
      </p>
    </section>

    <!-- 3Cat -->
    <section class="mt-16 max-w-[70ch]">
      <h2
        class="mb-4 border-b border-rule pb-2 font-mono text-[11px] font-medium uppercase tracking-[0.16em] text-ink-3"
      >
        Reproductor de 3Cat
      </h2>
      <p class="font-serif text-lg leading-relaxed text-ink">
        Els episodis s'escolten amb el reproductor oficial de 3Cat, integrat a la pàgina de cada
        episodi. Quan hi accedeixes, el teu navegador es connecta a 3Cat, que pot fer servir galetes
        i eines d'analítica pròpies. Aquest reproductor es regeix per la <a
          href="https://www.3cat.cat/avis-legal/privacitat/dades/"
          target="_blank"
          rel="noopener noreferrer"
          class={linkClass}>política de privadesa de 3Cat</a
        >.
      </p>
    </section>
  </article>
</div>
