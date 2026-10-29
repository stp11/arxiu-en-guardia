import { getLocationStats, getLocations } from "#client";
import { error } from "@sveltejs/kit";

import type { PageLoad } from "./$types";

export const load: PageLoad = async () => {
  const [response, statsResponse] = await Promise.all([getLocations(), getLocationStats()]);

  // There's no response when the API can't be reached.
  if (response.error || !response.data) {
    throw error(response.response?.status ?? 503);
  }

  // The map works without the count.
  return { locations: response.data, stats: statsResponse.data ?? null };
};
