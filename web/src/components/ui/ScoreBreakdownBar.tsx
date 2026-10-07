import { Box, Typography } from "@mui/material";
import { useTokens } from "../../theme/useTokens";

export interface Segment {
  label: string;
  /** Points earned. */
  value: number;
  /** Points available (the weight of the criterion). */
  max: number;
}

interface Props {
  segments: Segment[];
  /** Digits shown for points, e.g. 2 gives 0.43. */
  digits?: number;
  dense?: boolean;
}

/**
 * Score broken down by criterion. Each criterion owns a slice of the bar as wide as its weight
 * (60 % / 20 % / 20 %); the filled part shows how many of its points were earned.
 */
export default function ScoreBreakdownBar({ segments, digits = 2, dense = false }: Props) {
  const p = useTokens();
  const total = segments.reduce((sum, s) => sum + s.max, 0) || 1;
  const earned = segments.reduce((sum, s) => sum + s.value, 0);
  const colors = [p.primary, p.info, p.success, p.warning];
  const summary = segments.map((s) => `${s.label} ${s.value.toFixed(digits)} sur ${s.max.toFixed(digits)}`).join(", ");

  return (
    <Box>
      <Box
        role="img"
        aria-label={`Total ${earned.toFixed(digits)} sur ${total.toFixed(digits)} : ${summary}`}
        sx={{ display: "flex", gap: 0.5, height: dense ? 8 : 12 }}
      >
        {segments.map((s, i) => (
          <Box
            key={s.label}
            sx={{ flex: s.max / total, bgcolor: p.surfaceAlt, borderRadius: 6, overflow: "hidden", border: `1px solid ${p.border}` }}
          >
            <Box
              sx={{
                width: `${s.max > 0 ? Math.min(1, s.value / s.max) * 100 : 0}%`, height: "100%",
                bgcolor: colors[i % colors.length],
                transition: "width 200ms ease",
              }}
            />
          </Box>
        ))}
      </Box>
      <Box component="ul" sx={{ listStyle: "none", m: 0, mt: 1, p: 0, display: "grid", gap: 0.5 }}>
        {segments.map((s, i) => (
          <Box component="li" key={s.label} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Box aria-hidden="true" sx={{ width: 10, height: 10, borderRadius: 3, bgcolor: colors[i % colors.length], flexShrink: 0 }} />
            <Typography variant="body2" sx={{ flex: 1 }}>
              {s.label}
              <Typography component="span" variant="caption" color="text.secondary">
                {" "}({Math.round((s.max / total) * 100)} % du score)
              </Typography>
            </Typography>
            <Typography variant="body2" sx={{ fontVariantNumeric: "tabular-nums", fontWeight: 500 }}>
              {s.value.toFixed(digits)} / {s.max.toFixed(digits)}
            </Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
}
