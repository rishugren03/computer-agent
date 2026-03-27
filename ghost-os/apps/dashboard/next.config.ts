import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@ghost-os/database"]
};

export default nextConfig;
