import { useParams, useNavigate, Link as RouterLink, Outlet, useLocation, useOutletContext, Navigate } from "react-router-dom";
import { Alert, Avatar, Box, Button, IconButton, Tooltip, Typography } from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import ContentCopyIcon from "@mui/icons-material/ContentCopyOutlined";
import HistoryIcon from "@mui/icons-material/HistoryOutlined";
import { api, CaseData, StageKey } from "../../api";
import { useAuth } from "../../auth";
import { CASE_TYPE_LABEL } from "../../format";
import { useLoad } from "../../hooks";
import { fonts } from "../../theme/tokens";
import { useTokens } from "../../theme/useTokens";
import { SkeletonCards } from "../../components/ui/Page";
import StatusChip from "../../components/ui/StatusChip";
import { useToast } from "../../components/ui/Toast";
import WorkflowStepper from "../../components/ui/WorkflowStepper";
import { CASE_ICON, displayStatus, PriorityChip } from "../Home";

export interface CaseContext {
  data: CaseData;
  reload: () => Promise<void>;
}

/** The case loaded by the layout, available to every step. */
export const useCase = () => useOutletContext<CaseContext>();

const STEP_KEYS: StageKey[] = ["mandat", "experts", "contrat", "preparation", "analyse", "rapport"];

function CaseId({ id }: { id: string }) {
  const p = useTokens();
  const toast = useToast();
  async function copy() {
    try {
      await navigator.clipboard.writeText(id);
      toast.success("Identifiant du dossier copié.");
    } catch {
      toast.error("Copie impossible.");
    }
  }
  return (
    <Box sx={{ display: "inline-flex", alignItems: "center", gap: 0.5 }}>
      <Typography component="code" sx={{ fontFamily: fonts.mono, fontSize: 12, bgcolor: p.surfaceAlt, border: `1px solid ${p.border}`, borderRadius: 1.5, px: 1, py: 0.25 }}>
        {id.slice(0, 8)}
      </Typography>
      <Tooltip title="Copier l'identifiant complet">
        <IconButton size="small" onClick={copy} aria-label="Copier l'identifiant du dossier"><ContentCopyIcon sx={{ fontSize: 16 }} /></IconButton>
      </Tooltip>
    </Box>
  );
}

export default function CaseLayout() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const p = useTokens();
  const loaded = useLoad(() => api.getCase(id), [id]);

  if (loaded.loading && !loaded.data) return <SkeletonCards count={3} height={110} />;
  if (loaded.error || !loaded.data) {
    return (
      <Box>
        <Alert severity="error" sx={{ mb: 2 }}>{loaded.error || "Dossier introuvable."}</Alert>
        <Button component={RouterLink} to="/" startIcon={<ArrowBackIcon />}>Retour à l'accueil</Button>
      </Box>
    );
  }

  const c = loaded.data;
  const last = location.pathname.split("/").filter(Boolean).pop() as string;
  const active = (STEP_KEYS as string[]).includes(last) ? (last as StageKey) : null;
  const onAudit = last === "audit";
  const Icon = CASE_ICON[c.case_type];

  // Opening the case lands on the step where work continues (investigators skip the mandate steps).
  if (location.pathname === `/cases/${id}`) {
    const current = c.stages.find((s) => s.current)?.key ?? "rapport";
    const landing = user?.role === "investigateur" && (current === "mandat" || current === "experts" || current === "contrat") ? "preparation" : current;
    return <Navigate to={`/cases/${id}/${landing}`} replace />;
  }

  return (
    <Box>
      <Button component={RouterLink} to="/" startIcon={<ArrowBackIcon />} size="small" sx={{ mb: 1.5, ml: -1 }}>
        {user?.role === "investigateur" ? "Mes missions" : "Tableau de bord"}
      </Button>
      <Box sx={{ display: "flex", gap: 2, alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", mb: 3 }}>
        <Box sx={{ display: "flex", gap: 2, alignItems: "center", minWidth: 0 }}>
          <Avatar variant="rounded" sx={{ bgcolor: p.primarySoft, color: p.primarySoftText, width: 52, height: 52 }}><Icon /></Avatar>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="h1" component="h1" sx={{ fontSize: { xs: 20, sm: 24 } }}>{CASE_TYPE_LABEL[c.case_type]}</Typography>
            <Box sx={{ display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap", mt: 0.5 }}>
              <StatusChip status={displayStatus(c)} />
              <PriorityChip priority={c.priority} />
              <Typography variant="body2" color="text.secondary">{c.mandataire.nom}, {c.mandataire.fonction}</Typography>
              <CaseId id={c.case_id} />
            </Box>
          </Box>
        </Box>
        <Button component={RouterLink} to={`/cases/${id}/audit`} variant={onAudit ? "contained" : "outlined"} startIcon={<HistoryIcon />}>
          Journal d'audit
        </Button>
      </Box>

      <Box sx={{ bgcolor: "background.paper", border: `1px solid ${p.border}`, borderRadius: 2.5, p: { xs: 1.5, sm: 2.5 }, mb: 4 }}>
        <WorkflowStepper stages={c.stages} activeKey={active ?? "mandat"} onSelect={(key) => navigate(`/cases/${id}/${key}`)} />
      </Box>

      <Outlet context={{ data: c, reload: loaded.reload } satisfies CaseContext} />
    </Box>
  );
}
