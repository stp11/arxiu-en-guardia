import type { ExpressionSpecification, MapLibreMap } from "maplibre-gl";

export const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";

export type Palette = Record<
  "paper" | "paper2" | "edge" | "ink2" | "ink3" | "rule" | "teal" | "moss" | "vermillion",
  string
>;

// The site's tokens, so the map follows the theme toggle.
export const readPalette = (): Palette => {
  const css = getComputedStyle(document.documentElement);
  const token = (name: string) => css.getPropertyValue(`--${name}`).trim();
  return {
    paper: token("paper"),
    paper2: token("paper-2"),
    edge: token("paper-edge"),
    ink2: token("ink-2"),
    ink3: token("ink-3"),
    rule: token("rule"),
    teal: token("teal"),
    moss: token("moss"),
    vermillion: token("vermillion-deep"),
  };
};

const mix = (from: string, to: string, amount: number) => {
  const rgb = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  const [a, b] = [rgb(from), rgb(to)];
  return `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * amount)).join(",")})`;
};

// Road names, shields and airports clutter a map of history.
const HIDDEN = /^(highway-name|highway-shield|road_shield|airport)/;

const CATALAN_NAME: ExpressionSpecification = [
  "coalesce",
  ["get", "name:ca"],
  ["get", "name:latin"],
  ["get", "name"],
];

// Recolours OpenFreeMap's Positron with the paper palette.
export const paintBasemap = (map: MapLibreMap, p: Palette) => {
  const water = mix(p.paper, p.teal, 0.2);
  const green = mix(p.paper, p.moss, 0.1);
  const road = mix(p.paper, p.rule, 0.5);

  for (const layer of map.getStyle().layers) {
    const { id, type } = layer;
    if (type !== "background" && layer.source !== "openmaptiles") continue;

    if (HIDDEN.test(id)) {
      map.setLayoutProperty(id, "visibility", "none");
    } else if (type === "background") {
      map.setPaintProperty(id, "background-color", p.paper);
    } else if (id === "water") {
      map.setPaintProperty(id, "fill-color", water);
    } else if (id === "waterway") {
      map.setPaintProperty(id, "line-color", water);
    } else if (id === "park" || id === "landcover_wood") {
      map.setPaintProperty(id, "fill-color", green);
    } else if (id === "building") {
      map.setPaintProperty(id, "fill-color", p.paper2);
      map.setPaintProperty(id, "fill-outline-color", p.edge);
    } else if (type === "fill") {
      map.setPaintProperty(id, "fill-color", mix(p.paper, p.paper2, 0.5));
    } else if (id.startsWith("boundary")) {
      map.setPaintProperty(id, "line-color", mix(p.paper, p.ink3, 0.45));
    } else if (type === "line") {
      map.setPaintProperty(id, "line-color", road);
    } else if (type === "symbol") {
      const strong = id.startsWith("label_country") || id === "label_city_capital";
      const color = id.startsWith("water_name") ? mix(p.teal, p.paper, 0.2) : p.ink3;
      map.setLayoutProperty(id, "text-field", CATALAN_NAME);
      map.setPaintProperty(id, "text-color", strong ? p.ink2 : color);
      map.setPaintProperty(id, "text-halo-color", p.paper);
    }
  }
};
