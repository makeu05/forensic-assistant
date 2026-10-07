import { useMemo, useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import {
  Alert, Avatar, Box, Button, Card, CardActionArea, CardContent, Chip, LinearProgress, Link, Paper, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, ToggleButton, ToggleButtonGroup, Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import AccountBalanceIcon from "@mui/icons-material/AccountBalanceOutlined";
import BugReportIcon from "@mui/icons-material/BugReportOutlined";
import FolderIcon from "@mui/icons-material/FolderOpenOutlined";
import LanIcon from "@mui/icons-material/LanOutlined";
import { api, CaseData, CaseType, Mission, Priority } from "../api";
import { useAuth } from "../auth";
import { CASE_TYPE_LABEL, formatDate, PRIORITY_LABEL, relativeTime } from "../format";
import { useLoad } from "../hooks";
import { useTokens } from "../theme/useTokens";
import { EmptyState, PageHeader, SkeletonCards } from "../components/ui/Page";
import ScoreRing from "../components/ui/ScoreRing";
import StatusChip, { Status } from "../components/ui/StatusChip";

export const CASE_ICON: Record<CaseType, typeof LanIcon> = {
  fraude_bancaire: AccountBalanceIcon,
  intrusion_reseau: LanIcon,
  malware: BugReportIcon,
};

export function PriorityChip({ priority }: { priority: Priority }) {
  const p = useTokens();
  const tone = { haute: [p.dangerSoft, p.dangerText], moyenne: [p.warningSoft, p.warningText], basse: [p.slateSoft, p.slateText] }[priority];
  return <Chip size="small" label={`Priorité ${PRIORITY_LABEL[priority].toLowerCase()}`} sx={{ bgcolor: tone[0], color: tone[1] }} />;
}

/** A finished final report means the case is done, whatever the server's coarse status says. */
export const displayStatus = (c: CaseData): Status =>
  c.stages.find((s) => s.key === "rapport")?.done ? "termine" : c.status;

function CaseCard({ c }: { c: CaseData }) {
  const p = useTokens();
  const Icon = CASE_ICON[c.case_type];
  const current = c.stages.find((s) => s.current);
  return (
    <Card sx={{ height: "100%", transition: "box-shadow 150ms ease, border-color 150ms ease", "&:hover": { boxShadow: 3, borderColor: p.primary } }}>
      <CardActionArea component={RouterLink} to={`/cases/${c.case_id}`} sx={{ height: "100%", display: "block" }} aria-label={`Ouvrir le dossier ${CASE_TYPE_LABEL[c.case_type]}`}>
        <CardContent sx={{ p: 3, display: "flex", flexDirection: "column", gap: 2, height: "100%" }}>
          <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 1 }}>
            <Avatar variant="rounded" sx={{ bgcolor: p.primarySoft, color: p.primarySoftText, width: 44, height: 44 }}><Icon /></Avatar>
            <StatusChip status={displayStatus(c)} />
          </Box>
          <Box>
            <Typography variant="h3" component="h2">{CASE_TYPE_LABEL[c.case_type]}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
              {c.description}
            </Typography>
          </Box>
          <PriorityChip priority={c.priority} />
          <Box sx={{ mt: "auto" }}>
            <Box sx={{ display: "flex", justifyContent: "space-between", mb: 0.75 }}>
              <Typography variant="caption" color="text.secondary">{current ? `Étape en cours : ${current.label}` : "Toutes les étapes sont terminées"}</Typography>
              <Typography variant="caption" sx={{ fontWeight: 500 }}>{Math.round(c.progress * 100)} %</Typography>
            </Box>
            <LinearProgress variant="determinate" value={c.progress * 100} aria-label={`Avancement du dossier : ${Math.round(c.progress * 100)} %`} color={c.progress === 1 ? "success" : "primary"} />
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
              Dernière activité {relativeTime(c.last_activity)}
            </Typography>
          </Box>
        </CardContent>
      </CardActionArea>
    </Card>
  );
}

function MandataireHome() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const cases = useLoad(() => api.listCases(), []);
  const [filter, setFilter] = useState<"all" | "open" | "done">("all");

  const shown = useMemo(() => {
    const list = cases.data ?? [];
    if (filter === "done") return list.filter((c) => displayStatus(c) === "termine");
    if (filter === "open") return list.filter((c) => displayStatus(c) !== "termine");
    return list;
  }, [cases.data, filter]);

  const open = (cases.data ?? []).filter((c) => displayStatus(c) !== "termine").length;
  const firstName = user?.display_name.split(" ")[0] ?? "";

  return (
    <>
      <PageHeader
        title="Tableau de bord"
        subtitle={cases.data ? `Bonjour ${firstName}. ${cases.data.length === 0 ? "Aucun dossier pour le moment." : `${open} dossier(s) en cours sur ${cases.data.length}.`}` : " "}
        actions={<Button variant="contained" size="large" startIcon={<AddIcon />} onClick={() => navigate("/cases/new")}>Nouveau mandat</Button>}
      />
      {cases.error && <Alert severity="error" sx={{ mb: 2 }}>{cases.error}</Alert>}
      {cases.loading && !cases.data && <SkeletonCards count={3} height={200} />}
      {cases.data && cases.data.length === 0 && (
        <EmptyState icon={<FolderIcon fontSize="large" />} title="Aucun mandat pour le moment"
          text="Un mandat décrit l'investigation à mener. Locard vous propose ensuite trois experts adaptés et vous guide jusqu'au rapport."
          action={{ label: "Créer un premier mandat", onClick: () => navigate("/cases/new") }} />
      )}
      {cases.data && cases.data.length > 0 && (
        <>
          <ToggleButtonGroup exclusive size="small" value={filter} onChange={(_, v) => v && setFilter(v)} aria-label="Filtrer les dossiers" sx={{ mb: 3 }}>
            <ToggleButton value="all">Tous</ToggleButton>
            <ToggleButton value="open">En cours</ToggleButton>
            <ToggleButton value="done">Terminés</ToggleButton>
          </ToggleButtonGroup>
          {shown.length === 0 ? (
            <Typography color="text.secondary">Aucun dossier dans cette catégorie.</Typography>
          ) : (
            <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", md: "repeat(2, 1fr)", lg: "repeat(3, 1fr)" } }}>
              {shown.map((c) => <CaseCard key={c.case_id} c={c} />)}
            </Box>
          )}
        </>
      )}
    </>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <Card sx={{ p: 2.5, flex: 1, minWidth: 150 }}>
      <Typography variant="h1" component="p" sx={{ lineHeight: 1 }}>{value}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{label}</Typography>
    </Card>
  );
}

function InvestigatorHome() {
  const navigate = useNavigate();
  const missions = useLoad(() => api.missions(), []);
  const requests = useLoad(() => api.myRequests(), []);
  const pending = (requests.data ?? []).filter((r) => r.status === "pending").length;
  const list: Mission[] = missions.data ?? [];

  return (
    <>
      <PageHeader title="Mes missions" subtitle="Les dossiers pour lesquels vous avez été choisi comme expert." />
      {pending > 0 && (
        <Alert severity="info" sx={{ mb: 3 }} action={<Button size="small" color="inherit" onClick={() => navigate("/demandes")}>Voir les demandes</Button>}>
          {pending === 1 ? "Une demande de mission attend votre réponse." : `${pending} demandes de mission attendent votre réponse.`}
        </Alert>
      )}
      {missions.error && <Alert severity="error" sx={{ mb: 2 }}>{missions.error}</Alert>}
      {missions.loading && !missions.data && <SkeletonCards count={3} height={72} />}
      {missions.data && list.length === 0 && (
        <EmptyState icon={<FolderIcon fontSize="large" />} title="Aucune mission pour le moment"
          text="Une mission apparaît ici dès qu'un mandataire vous choisit après votre acceptation d'une demande."
          action={pending > 0 ? { label: "Répondre aux demandes", onClick: () => navigate("/demandes") } : undefined} />
      )}
      {list.length > 0 && (
        <>
          <Box sx={{ display: "flex", gap: 2, mb: 3, flexWrap: "wrap" }}>
            <Stat label="Missions" value={list.length} />
            <Stat label="PV analysés" value={list.reduce((n, m) => n + m.pv_count, 0)} />
            <Stat label="Incohérences détectées" value={list.reduce((n, m) => n + m.incoherence_count, 0)} />
            <Stat label="Sévérité haute" value={list.reduce((n, m) => n + m.high_severity_count, 0)} />
          </Box>
          <Paper variant="outlined">
            <TableContainer>
              <Table size="small" aria-label="Missions en cours" sx={{ "& td, & th": { fontSize: 14 } }}>
                <TableHead>
                  <TableRow>
                    <TableCell>Dossier</TableCell>
                    <TableCell>Statut</TableCell>
                    <TableCell align="right">PV</TableCell>
                    <TableCell align="right">Incohérences</TableCell>
                    <TableCell align="center">Cohérence</TableCell>
                    <TableCell>Dernier PV</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {list.map((m) => (
                    <TableRow key={m.case_id} hover>
                      <TableCell>
                        <Link component={RouterLink} to={`/cases/${m.case_id}/analyse`} underline="hover" sx={{ fontWeight: 500 }}>
                          {CASE_TYPE_LABEL[m.case_type]}
                        </Link>
                        <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
                          {PRIORITY_LABEL[m.priority]} · ouvert le {formatDate(m.created_at)}
                        </Typography>
                      </TableCell>
                      <TableCell><StatusChip status={m.status} /></TableCell>
                      <TableCell align="right">{m.pv_count}</TableCell>
                      <TableCell align="right">
                        {m.incoherence_count}
                        {m.high_severity_count > 0 && <Typography component="span" variant="caption" color="error"> ({m.high_severity_count} haute)</Typography>}
                      </TableCell>
                      <TableCell align="center">
                        {m.score_coherence === null ? <Typography variant="caption" color="text.secondary">Aucun PV</Typography>
                          : <ScoreRing value={m.score_coherence} size={44} label="Cohérence des témoignages" caption="%" good={0.8} fair={0.6} />}
                      </TableCell>
                      <TableCell>{m.last_pv_at ? relativeTime(m.last_pv_at) : "Aucun"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </>
      )}
    </>
  );
}

export default function Home() {
  const { user } = useAuth();
  return user?.role === "investigateur" ? <InvestigatorHome /> : <MandataireHome />;
}
