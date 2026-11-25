"use client";
import { Button } from "@/components/ui";

export default function PageError({
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <main id="content" className="shell">
      <h1>Overview unavailable</h1>
      <p>The page could not be displayed.</p>
      <Button onClick={reset}>Try again</Button>
    </main>
  );
}
