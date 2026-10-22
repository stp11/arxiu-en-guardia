<script lang="ts">
  import { ArrowLeft } from "@lucide/svelte";
  import { SITE_NAME, SITE_URL } from "src/lib/constants";

  import AppLogo from "lib/components/app-logo.svelte";

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
        Privadesa
      </span>
      <h1
        class="max-w-[18ch] font-serif text-[clamp(2.25rem,5.5vw,4.25rem)] font-medium text-balance leading-[1.05] tracking-[-0.015em]"
      >
        Política de privadesa
      </h1>
    </header>

    <!-- Intro -->
    <section class="mt-12 max-w-[70ch]">
      <p class="font-serif text-[clamp(1.2rem,2vw,1.625rem)] leading-snug text-pretty text-ink">
        Aquesta web no recull dades personals. No té formularis, comptes, galetes pròpies ni
        analítica que t'identifiqui.
      </p>
    </section>

    <!-- Preferències -->
    <section class="mt-16 max-w-[70ch]">
      <h2
        class="mb-4 border-b border-rule pb-2 font-mono text-[11px] font-medium uppercase tracking-[0.16em] text-ink-3"
      >
        Preferències al navegador
      </h2>
      <p class="font-serif text-lg leading-relaxed text-ink">
        L'única cosa que el web desa al teu dispositiu és si prefereixes el tema clar o el fosc. Es
        guarda a l'emmagatzematge local del navegador.
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
        consulten més. No fa servir galetes ni crea perfils dels visitants: només en veiem xifres
        agregades. Pots consultar la <a
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
        El web es distribueix a través de Cloudflare, que tracta dades tècniques de cada petició,
        com ara l'adreça IP o el navegador, per servir les pàgines i protegir-les d'abusos, d'acord
        amb la seva política de privadesa. Les dades de l'arxiu s'allotgen en un proveïdor de
        servidors. El nostre servidor no guarda registres de les visites.
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
        episodi. En obrir-la, el teu navegador es connecta a 3Cat, que pot fer servir galetes i
        eines d'analítica pròpies. Aquest reproductor es regeix per la <a
          href="https://www.3cat.cat/avis-legal/privacitat/dades/"
          target="_blank"
          rel="noopener noreferrer"
          class={linkClass}>política de privadesa de 3Cat</a
        >.
      </p>
    </section>
  </article>
</div>
