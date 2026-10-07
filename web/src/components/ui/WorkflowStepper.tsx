import { Box, ButtonBase, Typography } from "@mui/material";
import CheckIcon from "@mui/icons-material/Check";
import type { Stage, StageKey } from "../../api";
import { useTokens } from "../../theme/useTokens";

interface Props {
  stages: Stage[];
  /** The step being viewed. */
  activeKey: StageKey;
  onSelect: (key: StageKey) => void;
}

const STATE_TEXT = { done: "terminée", current: "en cours", todo: "à venir" } as const;

/**
 * The case lifecycle, always visible: Mandat > Experts > Contrat > Préparation > Analyse > Rapport.
 * A tick means the step's output exists, the highlighted number is where work continues, and the
 * step being viewed is underlined. On a phone the list scrolls sideways instead of wrapping.
 */
export default function WorkflowStepper({ stages, activeKey, onSelect }: Props) {
  const p = useTokens();
  return (
    <Box component="nav" aria-label="Étapes du dossier" sx={{ overflowX: "auto", pb: 0.5 }}>
      <Box component="ol" sx={{ display: "flex", alignItems: "flex-start", listStyle: "none", m: 0, p: 0, minWidth: 560 }}>
        {stages.map((stage, index) => {
          const state = stage.done ? "done" : stage.current ? "current" : "todo";
          const viewing = stage.key === activeKey;
          return (
            <Box component="li" key={stage.key} sx={{ flex: 1, display: "flex", alignItems: "flex-start", minWidth: 0 }}>
              <ButtonBase
                onClick={() => onSelect(stage.key)}
                aria-current={viewing ? "step" : undefined}
                sx={{
                  flexDirection: "column", gap: 0.75, px: 0.5, py: 0.5, borderRadius: 2, flex: 1, minWidth: 0,
                  transition: "background-color 150ms ease", "&:hover": { bgcolor: p.surfaceAlt },
                }}
              >
                <Box
                  aria-hidden="true"
                  sx={{
                    width: 32, height: 32, borderRadius: "50%", display: "grid", placeItems: "center", fontSize: 14, fontWeight: 600,
                    bgcolor: state === "done" ? p.success : state === "current" ? p.primary : "transparent",
                    color: state === "todo" ? p.textSecondary : "#FFFFFF",
                    border: `2px solid ${state === "done" ? p.success : state === "current" ? p.primary : p.border}`,
                    transition: "background-color 150ms ease",
                  }}
                >
                  {state === "done" ? <CheckIcon sx={{ fontSize: 18 }} /> : index + 1}
                </Box>
                <Typography
                  variant="body2"
                  sx={{
                    fontWeight: viewing ? 600 : 500, textAlign: "center", pb: 0.5,
                    color: viewing ? "text.primary" : "text.secondary",
                    borderBottom: `2px solid ${viewing ? p.primary : "transparent"}`,
                  }}
                >
                  {stage.label}
                  <Box component="span" sx={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)", whiteSpace: "nowrap" }}>
                    {" "}({STATE_TEXT[state]})
                  </Box>
                </Typography>
              </ButtonBase>
              {index < stages.length - 1 && (
                <Box
                  aria-hidden="true"
                  sx={{ flex: "0 0 24px", height: 2, mt: "21px", bgcolor: stage.done ? p.success : p.border, borderRadius: 1 }}
                />
              )}
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
