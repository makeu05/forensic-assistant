import { Box, Typography } from "@mui/material";
import { useTokens } from "../../theme/useTokens";

interface Props {
  /** 0 to 1 */
  value: number;
  size?: number;
  /** What the score measures, read by screen readers ("Score de l'expert"). */
  label?: string;
  /** Short caption under the number, e.g. "cohérence". */
  caption?: string;
  /** Score at or above `good` is green, at or above `fair` amber, below is red. */
  good?: number;
  fair?: number;
}

/** A circular score from 0 to 100. The number is always written, so the ring is a reinforcement, not the only cue. */
export default function ScoreRing({ value, size = 88, label = "Score", caption, good = 0.75, fair = 0.5 }: Props) {
  const p = useTokens();
  const clamped = Math.max(0, Math.min(1, value));
  const stroke = Math.max(6, Math.round(size / 11));
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const color = clamped >= good ? p.success : clamped >= fair ? p.warning : p.danger;
  const number = Math.round(clamped * 100);

  return (
    <Box
      role="img"
      aria-label={`${label} : ${number} sur 100`}
      sx={{ position: "relative", width: size, height: size, flexShrink: 0 }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={p.border} strokeWidth={stroke} />
        <circle
          cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={circumference * (1 - clamped)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: "stroke-dashoffset 200ms ease, stroke 200ms ease" }}
        />
      </svg>
      <Box sx={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <Typography component="span" sx={{ fontSize: Math.round(size * 0.28), lineHeight: 1, fontWeight: 600 }}>
          {number}
        </Typography>
        <Typography component="span" variant="caption" color="text.secondary" sx={{ lineHeight: 1.2, mt: 0.25 }}>
          {caption ?? "/ 100"}
        </Typography>
      </Box>
    </Box>
  );
}
