export function requirePublicApiUrl(value: string | undefined): URL {
  if (!value?.trim()) {
    throw new Error(
      "Set VITE_API_URL to the complete backend's public HTTPS URL before deploying.",
    );
  }
  const url = new URL(value.trim());
  const host = url.hostname.toLowerCase();
  if (
    url.protocol !== "https:" ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    host === "localhost" ||
    host.endsWith(".localhost") ||
    host.endsWith(".local") ||
    host === "[::1]" ||
    host === "[::]" ||
    /^(127\.|0\.|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.)/.test(
      host,
    )
  ) {
    throw new Error(
      "VITE_API_URL must be public HTTPS, without credentials, a query string or a fragment.",
    );
  }
  return url;
}
