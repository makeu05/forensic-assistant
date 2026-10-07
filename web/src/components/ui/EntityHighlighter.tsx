import { Box, Typography } from "@mui/material";
import type { EntityLabel, Segment } from "../../api";
import { entityStyles } from "../../theme/tokens";
import { useTokens } from "../../theme/useTokens";

interface Props {
  segments: Segment[];
  legend?: boolean;
  /** Reading size: 16 for a comfortable read, 14 for dense expert screens. */
  dense?: boolean;
}

const ORDER: EntityLabel[] = ["personne", "lieu", "date", "montant", "heure"];

/**
 * A witness statement with its named entities marked. Each kind has its own colour AND its own
 * underline style (solid, dashed, dotted, double, wavy), and a hidden label for screen readers,
 * so nothing depends on colour alone.
 */
export default function EntityHighlighter({ segments, legend = true, dense = false }: Props) {
  const p = useTokens();
  const styles = entityStyles(p);
  const counts = segments.reduce<Record<string, number>>((acc, s) => {
    if (s.label) acc[s.label] = (acc[s.label] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <Box>
      {legend && (
        <Box component="ul" aria-label="Légende des entités" sx={{ display: "flex", flexWrap: "wrap", gap: 1, listStyle: "none", m: 0, mb: 2, p: 0 }}>
          {ORDER.map((key) => (
            <Box component="li" key={key} sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
              <Box
                component="span"
                sx={{
                  bgcolor: styles[key].bg, color: styles[key].fg, px: 0.75, py: 0.25, borderRadius: 1, fontSize: 12, fontWeight: 500,
                  textDecoration: "underline", textDecorationStyle: styles[key].line as "solid", textUnderlineOffset: 3,
                }}
              >
                {styles[key].label}
              </Box>
              <Typography variant="caption" color="text.secondary">{counts[key] ?? 0}</Typography>
            </Box>
          ))}
        </Box>
      )}
      <Typography
        component="div"
        tabIndex={0}
        aria-label="Texte du procès-verbal avec entités repérées"
        sx={{ whiteSpace: "pre-wrap", lineHeight: 1.9, fontSize: dense ? 14 : 16, wordBreak: "break-word" }}
      >
        {segments.map((s, i) =>
          s.label ? (
            <Box
              component="mark"
              key={i}
              sx={{
                bgcolor: styles[s.label].bg, color: styles[s.label].fg, borderRadius: 0.75, px: 0.4, mx: "-0.1em",
                textDecoration: "underline", textDecorationStyle: styles[s.label].line as "solid", textUnderlineOffset: 4,
                textDecorationThickness: "1.5px",
              }}
            >
              {s.text}
              <Box component="span" sx={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>
                {" "}({styles[s.label].label})
              </Box>
            </Box>
          ) : (
            <span key={i}>{s.text}</span>
          ),
        )}
      </Typography>
    </Box>
  );
}
