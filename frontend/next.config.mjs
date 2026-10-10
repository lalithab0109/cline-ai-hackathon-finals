/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The Cline SDK (server-only, used by app/api/assistant) is ESM with
  // optional native/provider deps; load it from node_modules at runtime
  // instead of bundling it.
  serverExternalPackages: ["@cline/agents", "@cline/llms", "@cline/shared"],
};

export default nextConfig;
