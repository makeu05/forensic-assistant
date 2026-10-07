import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Alert, Box, Button, Card, CircularProgress, FormControl, InputLabel, MenuItem, Select, TextField, Typography,
} from "@mui/material";
import GppGoodIcon from "@mui/icons-material/GppGoodOutlined";
import HistoryIcon from "@mui/icons-material/HistoryOutlined";
import { api, AuditEntry, AuditFilters, CaseData } from "../api";
import { CASE_TYPE_LABEL, formatDateTime, frenchError, MODULE_LABEL, relativeTime } from "../format";
import { useLoad } from "../hooks";
import AuditTimeline from "../components/ui/AuditTimeline";
import { EmptyState, PageHeader, SectionTitle, SkeletonCards } from "../components/ui/Page";

const PAGE = 50;

interface Verdict {
  valid: boolean;
  entries: number;
  brokenAt: number | null;
  at: string;
}

/** The integrity check: replays the whole hash chain and says plainly whether it holds. */
function IntegrityCheck() {
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run() {
    setBusy(true);
    setError("");
    try {
      const r = await api.verifyChain();
      setVerdict({ valid: r.valid, entries: r.entries, brokenAt: r.broken_at, at: new Date().toISOString() });
    } catch (e) {
      setError(frenchError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card sx={{ p: 3, mb: 3 }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2, flexWrap: "wrap", alignItems: "center" }}>
        <Box sx={{ maxWidth: 640 }}>
          <Typography variant="h3" component="h2">Intégrité du journal</Typography>
          <Typography variant="body2" color="text.secondary">
            Chaque entrée contient l'empreinte de la précédente. Le contrôle rejoue toute la chaîne et signale la première entrée modifiée ou supprimée.
            Il porte sur l'ensemble du journal, tous dossiers confondus.
          </Typography>
        </Box>
        <Button variant="contained" startIcon={busy ? <CircularProgress size={18} color="inherit" /> : <GppGoodIcon />} onClick={run} disabled={busy}>
          {busy ? "Vérification…" : "Vérifier l'intégrité"}
        </Button>
      </Box>
      <Box role="status" aria-live="polite" sx={{ mt: verdict || error ? 2 : 0 }}>
        {error && <Alert severity="error">{error}</Alert>}
        {verdict?.valid && (
          <Alert severity="success">
            <strong>Chaîne intacte.</strong> {verdict.entries} entrées vérifiées, aucune altération détectée. Contrôle effectué le {formatDateTime(verdict.at)}.
          </Alert>
        )}
        {verdict && !verdict.valid && (
          <Alert severity="error">
            <strong>Altération détectée.</strong> La chaîne est rompue à l'entrée n° {verdict.brokenAt} (sur {verdict.entries} lues). Les entrées à partir de celle-ci ne sont plus fiables : prévenez l'administrateur.
          </Alert>
        )}
      </Box>
    </Card>
  );
}

function CaseAudit({ caseId }: { caseId: string }) {
  const [module, setModule] = useState("");
  const [actor, setActor] = useState("");
  const [action, setAction] = useState("");
  const [newestFirst, setNewestFirst] = useState(true);
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [modules, setModules] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const filters = (offset: number): AuditFilters => ({
    module: module || undefined, actor: actor.trim() || undefined, action: action.trim() || undefined,
    order: newestFirst ? "desc" : "asc", limit: PAGE, offset,
  });

  // Reload from the start when a filter changes (text filters wait a moment while typing).
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const timer = window.setTimeout(() => {
      api.auditLogs(caseId, filters(0))
        .then((r) => { if (!cancelled) { setEntries(r.logs); setTotal(r.total); setModules(r.modules); setError(""); } })
        .catch((e) => !cancelled && setError(frenchError(e)))
        .finally(() => !cancelled && setLoading(false));
    }, 250);
    return () => { cancelled = true; window.clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, module, actor, action, newestFirst]);

  async function more() {
    try {
      const r = await api.auditLogs(caseId, filters(entries.length));
      setEntries((prev) => [...prev, ...r.logs]);
    } catch (e) {
      setError(frenchError(e));
    }
  }

  return (
    <>
      <Card sx={{ p: 2.5, mb: 3 }}>
        <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", lg: "repeat(4, 1fr)" } }}>
          <FormControl size="small">
            <InputLabel id="audit-module">Module</InputLabel>
            <Select labelId="audit-module" label="Module" value={module} onChange={(e) => setModule(e.target.value)}>
              <MenuItem value="">Tous les modules</MenuItem>
              {modules.map((m) => <MenuItem key={m} value={m}>{m} · {MODULE_LABEL[m] ?? m}</MenuItem>)}
            </Select>
          </FormControl>
          <TextField size="small" label="Utilisateur" value={actor} onChange={(e) => setActor(e.target.value)} placeholder="adresse e-mail" />
          <TextField size="small" label="Action" value={action} onChange={(e) => setAction(e.target.value)} placeholder="par exemple analyze" />
          <FormControl size="small">
            <InputLabel id="audit-order">Ordre</InputLabel>
            <Select labelId="audit-order" label="Ordre" value={newestFirst ? "desc" : "asc"} onChange={(e) => setNewestFirst(e.target.value === "desc")}>
              <MenuItem value="desc">Plus récent d'abord</MenuItem>
              <MenuItem value="asc">Plus ancien d'abord</MenuItem>
            </Select>
          </FormControl>
        </Box>
      </Card>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {loading && entries.length === 0 && <SkeletonCards count={3} height={80} />}
      {!loading && entries.length === 0 && !error && (
        <EmptyState icon={<HistoryIcon fontSize="large" />} title="Aucune entrée" text="Aucune action ne correspond à ces filtres pour ce dossier." />
      )}
      {entries.length > 0 && (
        <>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }} aria-live="polite">{total} entrée(s) pour ce dossier</Typography>
          <AuditTimeline entries={entries} />
          {entries.length < total && <Box sx={{ textAlign: "center" }}><Button variant="outlined" onClick={more}>Afficher les entrées suivantes</Button></Box>}
        </>
      )}
    </>
  );
}

/** Screen 11: the append-only audit trail as a timeline, filterable, with the integrity check. */
export default function AuditPage() {
  const { id } = useParams();
  const cases = useLoad<CaseData[]>(() => (id ? Promise.resolve([]) : api.listCases()), [id]);
  const [picked, setPicked] = useState("");
  const caseId = id ?? (picked || cases.data?.[0]?.case_id || "");

  return (
    <>
      {id ? <SectionTitle>Journal d'audit</SectionTitle> : (
        <PageHeader title="Journal d'audit" subtitle="Qui a fait quoi, et quand, sur chaque dossier. Le journal est en ajout seul : il ne s'efface pas." />
      )}
      <IntegrityCheck />
      {!id && cases.data && cases.data.length > 0 && (
        <FormControl size="small" sx={{ mb: 3, minWidth: 300 }}>
          <InputLabel id="audit-case">Dossier</InputLabel>
          <Select labelId="audit-case" label="Dossier" value={caseId} onChange={(e) => setPicked(e.target.value)}>
            {cases.data.map((c) => (
              <MenuItem key={c.case_id} value={c.case_id}>{CASE_TYPE_LABEL[c.case_type]} · {relativeTime(c.created_at)}</MenuItem>
            ))}
          </Select>
        </FormControl>
      )}
      {!id && cases.loading && !cases.data && <SkeletonCards count={2} height={80} />}
      {!id && cases.data && cases.data.length === 0 && (
        <EmptyState icon={<HistoryIcon fontSize="large" />} title="Aucun dossier" text="Le journal d'un dossier apparaît dès sa création." />
      )}
      {caseId && <CaseAudit caseId={caseId} />}
    </>
  );
}
