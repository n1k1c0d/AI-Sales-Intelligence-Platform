import type { ButtonHTMLAttributes } from "react";
import type { LucideIcon } from "lucide-react";
import type { ServiceStatus } from "@/features/system-status/contract";

export type DisplayStatus = ServiceStatus | "checking";
export const labels = {
  operational: "Operational",
  degraded: "Degraded",
  unavailable: "Unavailable",
  unknown: "Unknown",
  checking: "Checking",
};

export function Button(props: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" className="button" {...props} />;
}
export function StatusBadge({
  status,
  label,
}: {
  status: DisplayStatus;
  label?: string;
}) {
  return (
    <span className={`status-badge tone-${status}`}>
      <i aria-hidden="true" />
      {label ?? labels[status]}
    </span>
  );
}
export function StatusCard({
  name,
  icon: Icon,
  color,
  status,
  label,
  description,
  detail,
}: {
  name: string;
  icon: LucideIcon;
  color: string;
  status: DisplayStatus;
  label?: string;
  description: string;
  detail: string;
}) {
  return (
    <article className="service-card">
      <div className="card-top">
        <span className={`icon-tile ${color}`}>
          <Icon size={21} strokeWidth={1.65} />
        </span>
        <StatusBadge status={status} label={label} />
      </div>
      <h3>{name}</h3>
      <p>{description}</p>
      <div className="card-detail">
        <span aria-hidden="true" className="term-sign">
          ›
        </span>
        <code>{detail}</code>
      </div>
    </article>
  );
}
