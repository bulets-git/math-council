/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const internalApiUrl = process.env.INTERNAL_API_URL || 'http://api:8000';
    return [
      {
        source: '/api/v1/:path*',
        destination: `${internalApiUrl}/api/v1/:path*`,
      },
      {
        source: '/health',
        destination: `${internalApiUrl}/health`,
      },
    ];
  },
};

export default nextConfig;
