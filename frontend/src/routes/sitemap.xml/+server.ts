import { SITE_URL } from "src/lib/constants";

import type { RequestHandler } from "./$types";

export const prerender = true;

type EpisodeRow = {
  id: number;
  slug: string | null;
  published_at: string | null;
};

type EpisodesPage = {
  items: EpisodeRow[];
  total: number;
  page: number;
  size: number;
  pages: number;
};

const PAGE_SIZE = 100;

const escapeXml = (value: string): string =>
  value.replace(/[<>&'"]/g, (c) => {
    switch (c) {
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case "&":
        return "&amp;";
      case "'":
        return "&apos;";
      case '"':
        return "&quot;";
      default:
        return c;
    }
  });

const fetchAllEpisodes = async (apiUrl: string, fetchFn: typeof fetch): Promise<EpisodeRow[]> => {
  const all: EpisodeRow[] = [];
  let page = 1;
  let totalPages = 1;

  do {
    const url = `${apiUrl}/api/episodes?page=${page}&size=${PAGE_SIZE}&order=desc`;
    const res = await fetchFn(url);
    if (!res.ok) {
      throw new Error(`Sitemap: failed to fetch episodes (page ${page}): ${res.status}`);
    }
    const data = (await res.json()) as EpisodesPage;
    all.push(...data.items);
    totalPages = data.pages;
    page += 1;
  } while (page <= totalPages);

  return all;
};

export const GET: RequestHandler = async ({ fetch }) => {
  const apiUrl = import.meta.env.VITE_API_URL;
  const episodes = await fetchAllEpisodes(apiUrl, fetch);

  const today = new Date().toISOString().slice(0, 10);

  const staticUrls: { loc: string; lastmod: string; priority: string; changefreq: string }[] = [
    { loc: `${SITE_URL}/`, lastmod: today, priority: "1.0", changefreq: "daily" },
    {
      loc: `${SITE_URL}/sobre-el-projecte`,
      lastmod: today,
      priority: "0.5",
      changefreq: "monthly",
    },
  ];

  const episodeUrls = episodes
    .filter((e) => e.slug)
    .map((e) => {
      const lastmod = e.published_at ? e.published_at.slice(0, 10) : today;
      return {
        loc: `${SITE_URL}/episodis/${e.id}/${e.slug}`,
        lastmod,
        priority: "0.7",
        changefreq: "yearly",
      };
    });

  const allUrls = [...staticUrls, ...episodeUrls];

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${allUrls
  .map(
    (u) =>
      `  <url>\n    <loc>${escapeXml(u.loc)}</loc>\n    <lastmod>${u.lastmod}</lastmod>\n    <changefreq>${u.changefreq}</changefreq>\n    <priority>${u.priority}</priority>\n  </url>`
  )
  .join("\n")}
</urlset>
`;

  return new Response(body, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
};
