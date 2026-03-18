/** @type {import('next').NextConfig} */
const nextConfig = {
  // Proxy API calls to the Python backend
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: "http://localhost:8000/api/v1/:path*",
      },
    ];
  },
};

module.exports = nextConfig;
