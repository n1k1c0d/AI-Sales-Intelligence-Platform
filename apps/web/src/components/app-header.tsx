import Image from "next/image";
import Link from "next/link";
import { LayoutDashboard } from "lucide-react";
import metadata from "../../package.json";

export function AppHeader() {
  return (
    <header className="app-header">
      <div className="bar">
        <Link className="brand" href="/" aria-label="DealMind overview">
          <Image src="/icon.svg" alt="" width={38} height={38} priority />
          <span>
            <strong>DealMind</strong>
            <small>AI Sales Intelligence Platform</small>
          </span>
        </Link>
        <nav aria-label="Main navigation">
          <Link href="/" aria-current="page">
            <LayoutDashboard size={15} />
            Overview
          </Link>
        </nav>
        <div className="build-info">
          <span className="dev-tag">
            <i /> Development
          </span>
          <span className="build-version">v{metadata.version}</span>
        </div>
      </div>
    </header>
  );
}
