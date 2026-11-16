/** Static export: FastAPI serves web/out on the same port as the API (one port = one tunnel). */
const nextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  reactStrictMode: true,
};
// `next dev` talks to the API on :8000; the exported build is served same-origin by FastAPI.
if (process.env.NODE_ENV === "development") {
  nextConfig.rewrites = async () => [{ source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" }];
}
export default nextConfig;
