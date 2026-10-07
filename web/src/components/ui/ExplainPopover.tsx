import { ReactNode, useId, useState } from "react";
import { Box, Button, Collapse, Popover, Typography } from "@mui/material";
import HelpIcon from "@mui/icons-material/HelpOutline";
import { fonts } from "../../theme/tokens";
import { useTokens } from "../../theme/useTokens";
import ScoreBreakdownBar, { Segment } from "./ScoreBreakdownBar";

interface Props {
  /** Button text. Defaults to "Pourquoi ?". */
  label?: string;
  title: string;
  /** The explanation in plain language. */
  children: ReactNode;
  /** Score breakdown, when the result is a score. */
  segments?: Segment[];
  /** Rule id or formula, hidden until asked for. */
  technical?: string;
}

/** "Pourquoi ?" : every algorithmic result can explain itself in plain language, with its breakdown on request. */
export default function ExplainPopover({ label = "Pourquoi ?", title, children, segments, technical }: Props) {
  const p = useTokens();
  const id = useId();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [showTech, setShowTech] = useState(false);

  return (
    <>
      <Button
        size="small"
        startIcon={<HelpIcon sx={{ fontSize: 18 }} />}
        onClick={(e) => setAnchor(e.currentTarget)}
        aria-haspopup="dialog"
        aria-expanded={Boolean(anchor)}
        aria-controls={anchor ? id : undefined}
        sx={{ minHeight: 28, px: 1 }}
      >
        {label}
      </Button>
      <Popover
        id={id}
        open={Boolean(anchor)}
        anchorEl={anchor}
        onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
        slotProps={{ paper: { role: "dialog", "aria-label": title, sx: { p: 2.5, maxWidth: 400, width: "calc(100vw - 32px)" } } as object }}
      >
        <Typography variant="h4" sx={{ mb: 1 }}>{title}</Typography>
        <Typography variant="body2" component="div" color="text.secondary" sx={{ mb: segments || technical ? 2 : 0 }}>
          {children}
        </Typography>
        {segments && <ScoreBreakdownBar segments={segments} />}
        {technical && (
          <Box sx={{ mt: 2 }}>
            <Button size="small" onClick={() => setShowTech((v) => !v)} aria-expanded={showTech} sx={{ minHeight: 28, px: 0.5 }}>
              {showTech ? "Masquer le détail technique" : "Détail technique"}
            </Button>
            <Collapse in={showTech}>
              <Typography component="code" sx={{ display: "block", mt: 1, p: 1, fontFamily: fonts.mono, fontSize: 12, bgcolor: p.surfaceAlt, borderRadius: 1.5, wordBreak: "break-word" }}>
                {technical}
              </Typography>
            </Collapse>
          </Box>
        )}
      </Popover>
    </>
  );
}
