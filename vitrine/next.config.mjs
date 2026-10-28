/** Site 100% estatico (out/): hospeda em qualquer lugar, sem servidor Node. */
export default {
  output: "export",
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || "",
  trailingSlash: true,
  images: { unoptimized: true },
};
