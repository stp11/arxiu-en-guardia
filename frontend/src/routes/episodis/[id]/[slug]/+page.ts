import { error, redirect } from "@sveltejs/kit";
import { getEpisodeApiEpisodesIdGet, getSimilarEpisodesApiEpisodesIdSimilarGet } from "src/client";

import type { PageLoad } from "./$types";

export const load: PageLoad = async ({ params }) => {
  const response = await getEpisodeApiEpisodesIdGet({
    path: {
      id: +params.id,
    },
  });

  if (response.error) {
    throw error(response.response.status);
  }

  // Validate slug and redirect to canonical URL if incorrect
  const episode = response.data;
  if (episode?.slug && params.slug !== episode.slug) {
    throw redirect(301, `/episodis/${params.id}/${episode.slug}`);
  }

  const similarResponse = await getSimilarEpisodesApiEpisodesIdSimilarGet({
    path: { id: +params.id },
    query: { limit: 3 },
  });

  return {
    episode: response.data,
    similarEpisodes: similarResponse.data ?? [],
  };
};
