<script lang="ts">
  import { onMount } from "svelte";
  import { fade } from "svelte/transition";

  import { replaceState } from "$app/navigation";
  import { page } from "$app/state";
  import { House, Loader2, Minus, Plus } from "@lucide/svelte";
  import {
    type ExpressionSpecification,
    type JumpToOptions,
    LngLat,
    type LngLatBoundsLike,
    MapLibreMap,
    MercatorCoordinate,
    Popup,
    setWorkerUrl,
  } from "maplibre-gl";
  import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
  import "maplibre-gl/dist/maplibre-gl.css";
  import { SITE_NAME, SITE_URL } from "src/lib/constants";

  import AppHero from "lib/components/app-hero.svelte";

  import { STYLE_URL, paintBasemap, readPalette, withoutTransitions } from "./basemap";
  import LocationCard from "./location-card.svelte";

  const { data } = $props();

  const locations = $derived(data.locations);
  // " de 869 dels 1.321 episodis" for the caption, or " dels episodis" without the count.
  const coverage = $derived(
    data.stats
      ? ` de ${data.stats.episodes.toLocaleString("ca")} dels ${data.stats.total.toLocaleString("ca")} episodis`
      : " dels episodis"
  );

  const title = `Mapa · ${SITE_NAME}`;
  const description =
    "Els llocs on passen les històries d'En Guàrdia, en un mapa amb els episodis de cada un.";
  const url = `${SITE_URL}/mapa`;

  // Coords dels Països Catalans aprox.
  const HOME: LngLatBoundsLike = [
    [-1.6, 37.8],
    [4.4, 42.95],
  ];
  const NORTH = 42.95;
  const PADDING = 16;
  const WEST = -3;
  const EAST = 8.6;
  // A place off the map opens zoomed out, among its neighbours.
  const AWAY_ZOOM = 4;

  const mercatorY = (lat: number) => MercatorCoordinate.fromLngLat([0, lat]).y;

  // Web Mercator ends at 85.05° and the poles lie infinitely beyond it, so
  // pins stay within 84°, whole on the map even fully zoomed out.
  const LATITUDE_LIMIT = 84;
  const position = (index: number): [number, number] => {
    const { longitude, latitude } = locations[index];
    return [longitude, Math.max(-LATITUDE_LIMIT, Math.min(LATITUDE_LIMIT, latitude))];
  };

  const homeCamera = (m: MapLibreMap): JumpToOptions => {
    const camera = m.cameraForBounds(HOME, { padding: PADDING });
    if (!camera?.center || camera.zoom === undefined) return {};
    const { lng, lat } = LngLat.convert(camera.center);
    const { clientWidth: width, clientHeight: height } = m.getContainer();
    const span = (width / (512 * 2 ** camera.zoom)) * 360;
    if (lng - span / 2 >= WEST) return camera;

    const shown = Math.min(span, EAST - WEST);
    const zoom = Math.log2(((width / shown) * 360) / 512);
    const worldSize = 512 * 2 ** zoom;
    const keepNorth = mercatorY(NORTH) + (height / 2 - PADDING) / worldSize;
    const y = Math.min(mercatorY(lat), keepNorth);
    return {
      ...camera,
      zoom,
      center: [WEST + shown / 2, new MercatorCoordinate(0, y).toLngLat().lat],
    };
  };

  let container: HTMLDivElement;
  let map: MapLibreMap | undefined;
  let selected = $state<number | null>(null);
  let loaded = $state(false);

  const selectedLocation = $derived(selected === null ? null : locations[selected]);

  const select = (index: number | null) => {
    if (selected !== null) {
      map?.setFeatureState({ source: "locations", id: selected }, { selected: false });
    }
    selected = index;
    if (index !== null) {
      map?.setFeatureState({ source: "locations", id: index }, { selected: true });
    }
    // In the URL, to share or reload; replaced, so Back leaves the map.
    replaceState(index === null ? page.url.pathname : `?location=${locations[index].slug}`, {});
  };

  // Grows with the square root, so the area tracks the episode count.
  const radius = (base: number, scale: number): ExpressionSpecification => [
    "+",
    base,
    ["*", scale, ["sqrt", ["get", "count"]]],
  ];

  // The site's own buttons, not MapLibre's, so they follow the theme.
  const controls = [
    { label: "Apropa", icon: Plus, action: () => map?.zoomIn() },
    { label: "Allunya", icon: Minus, action: () => map?.zoomOut() },
    {
      label: "Torna a la vista inicial",
      icon: House,
      // A fixed duration: by default the flight lengthens with the distance.
      action: () => {
        if (map) map.flyTo({ ...homeCamera(map), duration: 600 });
      },
    },
  ];

  const isSelected: ExpressionSpecification = ["boolean", ["feature-state", "selected"], false];

  const paint = () => {
    if (!map) return;
    const p = readPalette();
    paintBasemap(map, p);
    map.setPaintProperty("locations", "circle-color", ["case", isSelected, p.vermillion, p.teal]);
    map.setPaintProperty("locations", "circle-stroke-color", p.paper);
  };

  onMount(() => {
    setWorkerUrl(workerUrl);
    const instance = new MapLibreMap({
      container,
      minZoom: 1,
      maxZoom: 14,
      dragRotate: false,
      pitchWithRotate: false,
      touchPitch: false,
      locale: { "AttributionControl.ToggleAttribution": "Mostra l'atribució" },
    });
    map = instance;
    // Not the style option: only setStyle takes a transformStyle.
    instance.setStyle(STYLE_URL, { transformStyle: withoutTransitions });
    instance.jumpTo(homeCamera(instance));
    instance.touchZoomRotate.disableRotation();

    // As soon as the style arrives, before anything is drawn, so the first
    // frame is already in the site's palette and has the pins.
    instance.on("style.load", () => {
      instance.addSource("locations", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: locations.map((l, i) => ({
            type: "Feature",
            id: i,
            geometry: { type: "Point", coordinates: position(i) },
            properties: { count: l.count },
          })),
        },
      });
      instance.addLayer({
        id: "locations",
        type: "circle",
        source: "locations",
        // Smaller places on top, or Catalunya would cover them.
        layout: { "circle-sort-key": ["-", ["get", "count"]] },
        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            2,
            radius(2.5, 0.7),
            6,
            radius(4, 1.3),
            10,
            radius(6, 2),
          ],
          "circle-opacity": ["case", isSelected, 0.95, 0.7],
          "circle-stroke-width": 1,
        },
      });
      paint();

      // A location in the URL opens selected.
      const shared = locations.findIndex((l) => l.slug === page.url.searchParams.get("location"));
      if (shared !== -1) {
        select(shared);
        reveal(shared, 0);
      }
    });
    // Every tile in, pins included: the cover lifts.
    instance.on("load", () => (loaded = true));

    const tooltip = new Popup({
      closeButton: false,
      closeOnClick: false,
      offset: 10,
      className: "map-tooltip",
    });
    const label = document.createElement("span");
    label.className = "font-mono text-[10px] uppercase tracking-[0.08em] text-ink";

    instance.on("mousemove", "locations", (e) => {
      const index = e.features?.[0]?.id as number | undefined;
      if (index === undefined) return;
      const l = locations[index];
      instance.getCanvas().style.cursor = "pointer";
      label.textContent = `${l.name} · ${l.count}`;
      tooltip.setLngLat(position(index)).setDOMContent(label).addTo(instance);
    });
    instance.on("mouseleave", "locations", () => {
      instance.getCanvas().style.cursor = "";
      tooltip.remove();
    });

    // A few pixels of slack, so the smallest pins can be tapped. Of the
    // pins hit, the nearest wins, not the smallest one drawn on top; pins
    // a few pixels apart tie, and the one with more episodes wins, so
    // Barcelona beats El Molino until the map is zoomed in.
    instance.on("click", (e) => {
      const { x, y } = e.point;
      const hits = instance.queryRenderedFeatures(
        [
          [x - 8, y - 8],
          [x + 8, y + 8],
        ],
        { layers: ["locations"] }
      );
      const distance = (index: number) => {
        const pin = instance.project(position(index));
        return Math.round(Math.hypot(pin.x - x, pin.y - y) / 4);
      };
      const count = (index: number) => locations[index].count;
      const [nearest] = hits
        .map((f) => f.id as number)
        .sort((a, b) => distance(a) - distance(b) || count(b) - count(a));
      tooltip.remove();
      select(nearest ?? null);
      if (nearest !== undefined) reveal(nearest);
    });

    // The card covers the bottom of a phone's map and the left of a
    // desktop's; a pin it hides, or off the map, is panned into view.
    const reveal = (index: number, duration = 400) => {
      const center = position(index);
      const pin = instance.project(center);
      const { clientWidth: width, clientHeight: height } = container;
      const wide = window.matchMedia("(min-width: 768px)").matches;
      const [left, bottom] = wide ? [400, height] : [0, height * 0.45];
      const within = (from: number, to: number) =>
        pin.x > from && pin.x < width && pin.y > 0 && pin.y < to;
      if (within(left, bottom)) return;
      const offset: [number, number] = wide ? [200, 0] : [0, -height * 0.275];
      const zoom = within(0, height) ? instance.getZoom() : Math.min(instance.getZoom(), AWAY_ZOOM);
      instance.easeTo({ center, offset, zoom, duration });
    };

    const observer = new MutationObserver(paint);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

    return () => {
      observer.disconnect();
      instance.remove();
      map = undefined;
    };
  });
</script>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={description} />
  <link rel="canonical" href={url} />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
  <meta property="og:url" content={url} />
  <meta name="twitter:title" content={title} />
  <meta name="twitter:description" content={description} />
</svelte:head>

<svelte:window onkeydown={(e) => e.key === "Escape" && select(null)} />

<div class="mx-auto w-full max-w-screen-xl px-6 pt-8 pb-12 md:px-10 md:pt-14">
  <AppHero>
    {#snippet tagline()}
      Descobreix on van passar les batalles, les aventures<br />
      i les heroïcitats de la història de Catalunya i del món.
    {/snippet}
  </AppHero>

  <figure class="mt-9">
    <div class="map relative h-[72dvh] min-h-[440px] overflow-hidden border border-rule">
      <!-- MapLibre's stylesheet makes it position: relative, so no inset-0 -->
      <div bind:this={container} class="h-full w-full"></div>
      <!-- The map's own paper, so it appears whole rather than tile by tile -->
      {#if !loaded}
        <div
          out:fade={{ duration: 200 }}
          role="status"
          class="absolute inset-0 grid place-items-center bg-paper"
        >
          <span
            class="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3"
          >
            <Loader2 class="size-3 animate-spin" /> Carregant el mapa…
          </span>
        </div>
      {/if}
      <div
        class="absolute top-2.5 right-2.5 z-10 flex flex-col divide-y divide-rule border border-rule bg-popover"
      >
        {#each controls as control (control.label)}
          <button
            type="button"
            onclick={control.action}
            aria-label={control.label}
            title={control.label}
            class="grid size-8 place-items-center text-ink-2 hover:text-vermillion-deep"
          >
            <control.icon class="size-4" />
          </button>
        {/each}
      </div>
      {#if selectedLocation}
        <LocationCard location={selectedLocation} onclose={() => select(null)} />
      {/if}
    </div>

    <figcaption class="mt-3 text-[12.5px] leading-relaxed text-ink-3">
      Mapa aproximat{coverage}: hi falten els que no tenen localització, i els que en tenen més
      d'una hi surten repetits.
    </figcaption>
  </figure>
</div>

<style>
  :global(.map-tooltip .maplibregl-popup-content) {
    padding: 3px 8px;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--popover);
    box-shadow: none;
  }

  :global(.map-tooltip .maplibregl-popup-tip) {
    display: none;
  }

  /* The attribution in the site's colours; the extra class outranks MapLibre's */
  .map :global(.maplibregl-ctrl.maplibregl-ctrl-attrib) {
    background: var(--popover);
  }

  .map :global(.maplibregl-ctrl-attrib),
  .map :global(.maplibregl-ctrl-attrib a) {
    color: var(--ink-3);
  }

  :global(.dark) .map :global(.maplibregl-ctrl-attrib-button) {
    filter: invert(1);
  }
</style>
