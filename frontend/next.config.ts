import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone', // Required for Docker deployment
  // @ts-ignore
  allowedDevOrigins: ["aiqip.panarub.co.id"],
};

export default nextConfig;
