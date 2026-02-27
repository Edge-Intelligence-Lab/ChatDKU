import type { NextConfig } from "next";

const isDevMode = process.env.NODE_ENV === "development";
const proxyTarget =
  process.env.BACKEND_PUBLIC_URL || process.env.BACKEND_INTERNAL_URL;

const nextConfig: NextConfig = {
  // Only use static export in production
  ...(isDevMode ? {} : { output: "export" }),
  trailingSlash: true,
  
  // Images configuration
  images: {
    unoptimized: true,
  },
  
  // Add rewrites for development mode to proxy API calls
  ...(isDevMode && proxyTarget
    ? {
    async rewrites() {
      return [
        {
          source: '/api/:path*',
          destination: `${proxyTarget}/api/:path*`,
        },
        {
          source: '/user/:path*',
          destination: `${proxyTarget}/user/:path*`,
        },
        {
          source: '/user_files/:path*',
          destination: `${proxyTarget}/user_files/:path*`,
        },
        {
          source: '/dev/:path*',
          destination: `${proxyTarget}/dev/:path*`,
        },
      ];
    },
  }
    : {}),
};

export default nextConfig;
