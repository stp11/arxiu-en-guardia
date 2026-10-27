import type { Handle } from "@sveltejs/kit";

// app.html's title and preview tags, for the pages rendered in the browser.
// The comments around them stay: SvelteKit warns when comments go missing.
const SITE_META = /(<!-- site-meta:.*?-->).*?(<!-- \/site-meta -->)/s;

export const handle: Handle = ({ event, resolve }) =>
  resolve(event, {
    // The API client reads them to parse what load fetched during SSR.
    filterSerializedResponseHeaders: (name) => name === "content-type" || name === "content-length",
    // A page rendered on the server brings its own <title> and tags. Link
    // previews read the first ones, so the site's have to go.
    transformPageChunk: ({ html }) => {
      const head = html.slice(0, html.indexOf("</head>"));
      return head.split("<title>").length > 2 ? html.replace(SITE_META, "$1$2") : html;
    },
  });
