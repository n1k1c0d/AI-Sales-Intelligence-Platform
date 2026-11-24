import "server-only";

const dnsLabel = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/i;

function validHostname(host: string) {
  // URL already validated the syntax of bracketed IPv6 addresses.
  if (host.startsWith("[")) return true;
  const name = host.replace(/\.$/, "");
  return (
    name.length <= 253 && name.split(".").every((label) => dnsLabel.test(label))
  );
}

export function getConfig(
  env: Readonly<Record<string, string | undefined>> = process.env,
) {
  const raw = env.API_BASE_URL ?? "http://127.0.0.1:8000";
  const timeout = env.API_REQUEST_TIMEOUT_MS ?? "8000";
  if (!/^https?:\/\/[^/?#@\\\s]+\/?$/i.test(raw) || !/^\d+$/.test(timeout))
    return null;
  try {
    const url = new URL(raw);
    const timeoutMs = Number(timeout);
    if (!validHostname(url.hostname) || timeoutMs < 1 || timeoutMs > 60_000)
      return null;
    return { origin: url.origin, timeoutMs };
  } catch {
    return null;
  }
}
export type ServerConfig = NonNullable<ReturnType<typeof getConfig>>;
