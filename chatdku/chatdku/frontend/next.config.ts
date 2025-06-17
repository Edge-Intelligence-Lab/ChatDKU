import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'export',  // This enables static HTML export
  trailingSlash: true,      // <-- adds /about/index.html
  // If you're using basePath, add it here:
  // basePath: '',
  
  // If you have images, you might need this:
  images: {
    unoptimized: true,  // For static export
  },
  
  // If you need to disable trailing slashes:
  // trailingSlash: false,
  };

export default nextConfig;
