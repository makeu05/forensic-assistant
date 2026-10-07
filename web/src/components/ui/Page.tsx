import { ReactNode } from "react";
import { Box, Button, Skeleton, Stack, Typography } from "@mui/material";
import { useTokens } from "../../theme/useTokens";

/** Title block of a screen: one h1, an optional subtitle, and the single primary action on the right. */
export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: { xs: "stretch", sm: "flex-start" }, flexDirection: { xs: "column", sm: "row" }, gap: 2, mb: 3 }}>
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="h1" component="h1" sx={{ fontSize: { xs: 24, sm: 32 } }}>{title}</Typography>
        {subtitle && <Typography color="text.secondary" component="div" sx={{ mt: 0.5 }}>{subtitle}</Typography>}
      </Box>
      {actions && <Box sx={{ display: "flex", gap: 1, flexShrink: 0, alignItems: "center" }}>{actions}</Box>}
    </Box>
  );
}

/** A friendly empty state: what is missing, why, and what to do about it. */
export function EmptyState({ icon, title, text, action }: { icon: ReactNode; title: string; text: string; action?: { label: string; onClick: () => void } }) {
  const p = useTokens();
  return (
    <Box sx={{ textAlign: "center", py: 6, px: 2, border: `1px dashed ${p.border}`, borderRadius: 2.5, bgcolor: p.surface }}>
      <Box aria-hidden="true" sx={{ width: 56, height: 56, mx: "auto", mb: 2, display: "grid", placeItems: "center", borderRadius: "50%", bgcolor: p.primarySoft, color: p.primarySoftText }}>
        {icon}
      </Box>
      <Typography variant="h3" component="h2" sx={{ mb: 0.5 }}>{title}</Typography>
      <Typography color="text.secondary" sx={{ maxWidth: 440, mx: "auto", mb: action ? 3 : 0 }}>{text}</Typography>
      {action && <Button variant="contained" onClick={action.onClick}>{action.label}</Button>}
    </Box>
  );
}

/** Placeholder rows while data loads (announced once, not row by row). */
export function SkeletonCards({ count = 3, height = 120 }: { count?: number; height?: number }) {
  return (
    <Stack spacing={2} role="status" aria-label="Chargement en cours">
      {Array.from({ length: count }, (_, i) => <Skeleton key={i} variant="rounded" height={height} animation="wave" />)}
    </Stack>
  );
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 1.5, gap: 1, flexWrap: "wrap" }}>
      <Typography variant="h3" component="h2">{children}</Typography>
      {action}
    </Box>
  );
}
