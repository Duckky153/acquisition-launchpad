import type { BlockerSeverity, MappingStatus, ReadinessStatus, SequenceStepState } from "../types";
import { humanizeConstant, readinessLabel } from "../lib/format";

type PillValue = MappingStatus | ReadinessStatus | SequenceStepState | BlockerSeverity | "VERIFIED" | "INVALID";

interface StatusPillProps {
  value: PillValue;
  compact?: boolean;
}

export function StatusPill({ value, compact = false }: StatusPillProps): React.ReactElement {
  const label = value === "DATA_PREPARATION_READY" ? readinessLabel(value) : humanizeConstant(value);
  const tone =
    value === "APPROVED" || value === "COMPLETE" || value === "DATA_PREPARATION_READY" || value === "VERIFIED"
      ? "success"
      : value === "BLOCKING" || value === "INVALID"
        ? "danger"
        : value === "REJECTED" || value === "BLOCKED" || value === "NOT_READY"
          ? "warning"
          : "neutral";
  return <span className={`status-pill status-pill--${tone}${compact ? " status-pill--compact" : ""}`}>{label}</span>;
}
