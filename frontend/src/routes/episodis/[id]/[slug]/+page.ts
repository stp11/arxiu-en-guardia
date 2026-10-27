import { error, redirect } from "@sveltejs/kit";
import { getEpisodeApiEpisodesIdGet, getSimilarEpisodesApiEpisodesIdSimilarGet } from "src/client";

import type { PageLoad } from "./$types";

export const load: PageLoad = async ({ params }) => {
  // Fetched in parallel; the similar episodes are discarded if we error or redirect
  const [response, similarResponse] = await Promise.all([
    getEpisodeApiEpisodesIdGet({
      path: {
        id: +params.id,
      },
    }),
    getSimilarEpisodesApiEpisodesIdSimilarGet({
      path: { id: +params.id },
      query: { limit: 3 },
    }),
  ]);

  // There's no response when the API can't be reached.
  if (response.error) {
    throw error(response.response?.status ?? 503);
  }

  // Validate slug and redirect to canonical URL if incorrect
  const episode = response.data;
  if (episode?.slug && params.slug !== episode.slug) {
    throw redirect(301, `/episodis/${params.id}/${episode.slug}`);
  }

  return {
    episode: response.data,
    similarEpisodes: similarResponse.data ?? [],
  };
};
