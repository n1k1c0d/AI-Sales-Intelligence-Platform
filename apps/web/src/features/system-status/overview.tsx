import {
  Blocks,
  Boxes,
  Database,
  Globe2,
  Layers3,
  Server,
  Workflow,
} from "lucide-react";
import { StatusPanel } from "./panel";

function ProjectInfo() {
  const rows = [
    { icon: Boxes, label: "Project", value: "DealMind" },
    { icon: Layers3, label: "Phase", value: "Project Foundation" },
    { icon: Server, label: "Backend", value: "FastAPI" },
    { icon: Database, label: "Database", value: "PostgreSQL + pgvector" },
    { icon: Globe2, label: "Frontend", value: "Next.js" },
    { icon: Workflow, label: "Automation", value: "n8n · prepared" },
  ];
  return (
    <aside className="panel project-panel" aria-labelledby="project-title">
      <div className="panel-heading">
        <Blocks size={18} />
        <h2 id="project-title">Project information</h2>
      </div>
      <dl>
        {rows.map(({ icon: Icon, label, value }) => (
          <div key={label}>
            <dt>
              <Icon size={14} />
              {label}
            </dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}
export function SystemOverview() {
  return (
    <main className="shell" id="content">
      <div className="page-heading">
        <div className="eyebrow">
          <Layers3 size={14} />
          Project Foundation
        </div>
        <h1>System Overview</h1>
        <p>Monitor your DealMind infrastructure.</p>
      </div>
      <StatusPanel projectInfo={<ProjectInfo />} />
    </main>
  );
}
