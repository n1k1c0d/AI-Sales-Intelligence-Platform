import { z } from "zod";

export const healthSchema = z.object({
  status: z.literal("ok"),
  service: z.literal("dealmind-api"),
});
const check = z.enum(["ok", "not_ready"]);
export const readinessSchema = z
  .object({
    status: z.enum(["ready", "not_ready"]),
    checks: z.object({ application: check, database: check }),
  })
  .refine(
    ({ status, checks }) =>
      (status === "ready") ===
        (checks.application === "ok" && checks.database === "ok") &&
      !(checks.application === "not_ready" && checks.database === "ok"),
  );
export type HealthResponse = z.infer<typeof healthSchema>;
export type ReadinessResponse = z.infer<typeof readinessSchema>;
