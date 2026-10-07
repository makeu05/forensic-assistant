import { useState } from "react";
import { Box, Button, Chip, IconButton, Tooltip, Typography } from "@mui/material";
import CheckIcon from "@mui/icons-material/VerifiedOutlined";
import CopyIcon from "@mui/icons-material/ContentCopyOutlined";
import GppBadIcon from "@mui/icons-material/GppBadOutlined";
import HelpIcon from "@mui/icons-material/HelpOutline";
import { formatDateTime, shortHash } from "../../format";
import { fonts } from "../../theme/tokens";
import { useTokens } from "../../theme/useTokens";
import { useToast } from "./Toast";

interface Props {
  hash: string;
  label?: string;
  /** true: checked and matching. false: checked and different. undefined: not checked here. */
  verified?: boolean;
  timestamp?: string;
  /** One line only, for lists and tables. */
  compact?: boolean;
}

/** An integrity hash in monospace, with copy, an optional timestamp and a verified / altered badge. */
export default function HashBadge({ hash, label = "SHA-256", verified, timestamp, compact = false }: Props) {
  const p = useTokens();
  const toast = useToast();
  const [expanded, setExpanded] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(hash);
      toast.success("Empreinte copiée dans le presse-papiers.");
    } catch {
      toast.error("Copie impossible : sélectionnez l'empreinte et copiez-la à la main.");
    }
  }

  const badge =
    verified === true ? (
      <Chip size="small" icon={<CheckIcon sx={{ fontSize: 16 }} />} label="Vérifié"
        sx={{ bgcolor: p.successSoft, color: p.successText, "& .MuiChip-icon": { color: "inherit" } }} />
    ) : verified === false ? (
      <Chip size="small" icon={<GppBadIcon sx={{ fontSize: 16 }} />} label="Altéré"
        sx={{ bgcolor: p.dangerSoft, color: p.dangerText, "& .MuiChip-icon": { color: "inherit" } }} />
    ) : (
      <Chip size="small" icon={<HelpIcon sx={{ fontSize: 16 }} />} label="Non vérifié"
        sx={{ bgcolor: p.neutralSoft, color: p.neutralText, "& .MuiChip-icon": { color: "inherit" } }} />
    );

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 0.5, minWidth: 0 }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
        <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>{label}</Typography>
        <Typography
          component="code"
          title={hash}
          sx={{
            fontFamily: fonts.mono, fontSize: 12, bgcolor: p.surfaceAlt, border: `1px solid ${p.border}`,
            borderRadius: 1.5, px: 1, py: 0.25, wordBreak: "break-all", color: "text.primary",
          }}
        >
          {expanded ? hash : shortHash(hash)}
        </Typography>
        <Tooltip title="Copier l'empreinte complète">
          <IconButton size="small" onClick={copy} aria-label={`Copier l'empreinte ${label}`}>
            <CopyIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </Tooltip>
        {badge}
        {!compact && hash.length > 20 && (
          <Button size="small" onClick={() => setExpanded((v) => !v)} aria-expanded={expanded} sx={{ minHeight: 28 }}>
            {expanded ? "Réduire" : "Afficher en entier"}
          </Button>
        )}
      </Box>
      {timestamp && (
        <Typography variant="caption" color="text.secondary">
          Horodaté le {formatDateTime(timestamp)}
        </Typography>
      )}
    </Box>
  );
}
