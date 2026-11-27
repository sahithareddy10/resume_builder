/** @type {import('next').NextConfig} */
const nextConfig = {
 reactStrictMode: true,
 experimental: {
  proxyTimeout: 600000,
 },
 async rewrites() {
 return [
 {
 source: '/api/:path*',
 destination: 'http://localhost:8001/api/:path*',
 },
 ];
 },
 webpack: (config) => {
 config.resolve.alias = {
 ...(config.resolve.alias || {}),
 canvas: false,
 };
 return config;
 },
};

module.exports = nextConfig;
