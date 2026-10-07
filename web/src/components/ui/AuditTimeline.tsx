import { useState } from "react";
import { Box, Button, Chip, Collapse, Typography } from "@mui/material";
import type { AuditEntry } from "../../api";
import { auditActionLabel, formatDateTime, MODULE_LABEL } from "../../format";
import { fonts } from "../../theme/tokens";
import { useTokens } from "../../theme/useTokens";
import HashBadge from "./HashBadge";

interface Props {
  entries: AuditEntry[];
}

function Entry({ entry, last }: { entry: AuditEntry; last: boolean }) {
  const p = useTokens();
  const [open, setOpen] = useState(false);
  const moduleName = MODULE_LABEL[entry.module] ?? entry.module;
  const payload = Object.keys(entry.payload ?? {}).length ? JSON.stringify(entry.payload, null, 2) : null;

  return (
    <Box component="li" sx={{ display: "grid", gridTemplateColumns: "24px 1fr", columnGap: 1.5 }}>
      <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
        <Box aria-hidden="true" sx={{ width: 12, height: 12, borderRadius: "50%", bgcolor: p.primary, border: `3px solid ${p.primarySoft}`, mt: 0.75, boxSizing: "content-box" }} />
        {!last && <Box aria-hidden="true" sx={{ flex: 1, width: 2, bgcolor: p.border, mt: 0.5 }} />}
      </Box>
      <Box sx={{ pb: 3, minWidth: 0 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{auditActionLabel(entry.action)}</Typography>
          <Chip size="small" label={`${entry.module} · ${moduleName}`} sx={{ bgcolor: p.neutralSoft, color: p.neutralText }} />
        </Box>
        <Typography variant="body2" color="text.secondary">
          <time dateTime={entry.timestamp}>{formatDateTime(entry.timestamp)}</time>
          {" · "}par <Box component="span" sx={{ color: "text.primary" }}>{entry.user ?? "système"}</Box>
        </Typography>
        {entry.file && (
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", fontFamily: fonts.mono, mt: 0.5, wordBreak: "break-all" }}>
            {entry.file}
          </Typography>
        )}
        {entry.hash && <Box sx={{ mt: 0.75 }}><HashBadge hash={entry.hash} label="Fichier SHA-256" compact /></Box>}
        <Button size="small" onClick={() => setOpen((v) => !v)} aria-expanded={open} sx={{ mt: 0.5, px: 0.5, minHeight: 28 }}>
          {open ? "Masquer les détails" : "Détails techniques"}
        </Button>
        <Collapse in={open}>
          <Box sx={{ mt: 1, p: 1.5, bgcolor: p.surfaceAlt, border: `1px solid ${p.border}`, borderRadius: 2, fontFamily: fonts.mono, fontSize: 12, display: "grid", gap: 0.75, overflowX: "auto" }}>
            <div>entrée n° {entry.id}</div>
            <div>empreinte : {entry.entry_hash}</div>
            <div>précédente : {entry.prev_hash}</div>
            {payload && <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{payload}</pre>}
          </Box>
        </Collapse>
      </Box>
    </Box>
  );
}

/**
 * The append-only journal as a vertical timeline: who, what, when, in which module.
 * Each entry holds the hash of the one before it; the technical details show the link.
 */
export default function AuditTimeline({ entries }: Props) {
  return (
    <Box component="ol" aria-label="Journal d'audit" sx={{ listStyle: "none", m: 0, p: 0 }}>
      {entries.map((e, i) => <Entry key={e.id} entry={e} last={i === entries.length - 1} />)}
    </Box>
  );
}
