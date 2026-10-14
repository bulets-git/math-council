/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // We use Next.js Route Handlers in app/api/v1/[...path]/route.ts and app/health/route.ts
  // to dynamically proxy requests at runtime, reading INTERNAL_API_URL or NEXT_PUBLIC_API_URL.
};

export default nextConfig;
