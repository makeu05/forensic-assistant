import { Chip } from "@mui/material";
import ErrorIcon from "@mui/icons-material/ErrorOutline";
import InfoIcon from "@mui/icons-material/InfoOutlined";
import WarningIcon from "@mui/icons-material/ReportProblemOutlined";
import type { Severity } from "../../api";
import { useTokens } from "../../theme/useTokens";

const LABEL: Record<Severity, string> = { haute: "Sévérité haute", moyenne: "Sévérité moyenne", basse: "Sévérité basse" };
const ICON = { haute: ErrorIcon, moyenne: WarningIcon, basse: InfoIcon };

/** Severity of an inconsistency: haute (red), moyenne (amber), basse (blue-grey). Icon and text carry the meaning too. */
export default function SeverityChip({ severity, size = "small" }: { severity: Severity; size?: "small" | "medium" }) {
  const p = useTokens();
  const tone = {
    haute: { bg: p.dangerSoft, fg: p.dangerText },
    moyenne: { bg: p.warningSoft, fg: p.warningText },
    basse: { bg: p.slateSoft, fg: p.slateText },
  }[severity];
  const Icon = ICON[severity];
  return (
    <Chip
      size={size}
      icon={<Icon sx={{ fontSize: 16 }} />}
      label={LABEL[severity]}
      sx={{ bgcolor: tone.bg, color: tone.fg, "& .MuiChip-icon": { color: "inherit" } }}
    />
  );
}
