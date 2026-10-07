import { Chip } from "@mui/material";
import AccessTimeIcon from "@mui/icons-material/AccessTimeOutlined";
import AutorenewIcon from "@mui/icons-material/AutorenewOutlined";
import CheckCircleIcon from "@mui/icons-material/CheckCircleOutlined";
import CancelIcon from "@mui/icons-material/CancelOutlined";
import StarIcon from "@mui/icons-material/StarBorderOutlined";
import TaskAltIcon from "@mui/icons-material/TaskAltOutlined";
import { brand } from "../../theme/tokens";
import { useTokens } from "../../theme/useTokens";

export type Status = "en_attente" | "en_cours" | "termine" | "pending" | "accepted" | "refused" | "chosen";

type Tone = "neutral" | "primary" | "success" | "danger" | "navy" | "successOutline";

const CONFIG: Record<Status, { label: string; tone: Tone; icon: typeof AccessTimeIcon }> = {
  en_attente: { label: "En attente", tone: "neutral", icon: AccessTimeIcon },
  en_cours: { label: "En cours", tone: "primary", icon: AutorenewIcon },
  termine: { label: "Terminé", tone: "successOutline", icon: TaskAltIcon },
  pending: { label: "En attente", tone: "neutral", icon: AccessTimeIcon },
  accepted: { label: "Accepté", tone: "success", icon: CheckCircleIcon },
  refused: { label: "Refusé", tone: "danger", icon: CancelIcon },
  chosen: { label: "Choisi", tone: "navy", icon: StarIcon },
};

/** Case and solicitation status. Always icon + text, never colour alone. */
export default function StatusChip({ status, size = "small" }: { status: Status; size?: "small" | "medium" }) {
  const p = useTokens();
  const { label, tone, icon: Icon } = CONFIG[status];
  const styles = {
    neutral: { bg: p.neutralSoft, fg: p.neutralText, border: "transparent" },
    primary: { bg: p.primarySoft, fg: p.primarySoftText, border: "transparent" },
    success: { bg: p.successSoft, fg: p.successText, border: "transparent" },
    danger: { bg: p.dangerSoft, fg: p.dangerText, border: "transparent" },
    navy: { bg: brand.navy700, fg: "#FFFFFF", border: brand.navy700 },
    successOutline: { bg: "transparent", fg: p.successText, border: p.success },
  }[tone];
  return (
    <Chip
      size={size}
      icon={<Icon sx={{ fontSize: 16 }} />}
      label={label}
      sx={{
        bgcolor: styles.bg, color: styles.fg, border: `1px solid ${styles.border}`,
        "& .MuiChip-icon": { color: "inherit" },
      }}
    />
  );
}
