/** Static export: the built page is plain files served by the local backend.
 *  No server-side code, no image optimiser, nothing fetched from outside. */
const nextConfig = {
  output: "export",
  reactStrictMode: true,
  images: { unoptimized: true },
  devIndicators: false,
  poweredByHeader: false,
};

export default nextConfig;
