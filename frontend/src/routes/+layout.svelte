<script lang="ts">
  import { browser } from "$app/environment";
  import Footer from "$lib/components/app-footer.svelte";
  import Nav from "$lib/components/app-nav.svelte";
  import { QueryClient, QueryClientProvider } from "@tanstack/svelte-query";
  import "src/routes/layout.css";

  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        enabled: browser,
        gcTime: 5 * 60 * 1000,
        refetchOnWindowFocus: false,
        retry: 1,
      },
    },
  });

  let { children } = $props();
</script>

<QueryClientProvider client={queryClient}>
  <div class="relative z-[2] flex min-h-dvh flex-col">
    <Nav />
    <main class="flex-1">
      {@render children()}
    </main>
    <Footer />
  </div>
</QueryClientProvider>
