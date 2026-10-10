import { Box, Chip, Typography } from "@mui/material";
import { useTokens } from "../../theme/useTokens";

/** One quoted sentence of a witness statement, tagged with the PV it comes from. */
export default function Excerpt({ pv, text }: { pv: string; text: string }) {
  const p = useTokens();
  return (
    <Box sx={{ flex: 1, minWidth: 0, p: 1.5, borderRadius: 2, bgcolor: p.surfaceAlt, border: `1px solid ${p.border}` }}>
      <Chip size="small" label={`PV ${pv}`} sx={{ mb: 1, bgcolor: p.primarySoft, color: p.primarySoftText }} />
      <Typography variant="body2" component="blockquote" sx={{ m: 0, fontStyle: "italic", wordBreak: "break-word" }}>« {text} »</Typography>
    </Box>
  );
}
