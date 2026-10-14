/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  compress: false, // Let reverse proxy (Railway Hikari) handle compression cleanly
};

export default nextConfig;
