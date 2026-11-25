// The local production preview listens only on loopback. Docker runs server.js directly.
process.env.HOSTNAME = "127.0.0.1";
await import("../.next/standalone/server.js");
