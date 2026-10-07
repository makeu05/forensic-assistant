import { useEffect, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import {
  Alert, Avatar, Box, Button, Card, Chip, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, Stack,
  Tooltip, Typography,
} from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import EventAvailableIcon from "@mui/icons-material/EventAvailableOutlined";
import EventBusyIcon from "@mui/icons-material/EventBusyOutlined";
import HourglassIcon from "@mui/icons-material/HourglassEmpty";
import RadioButtonUncheckedIcon from "@mui/icons-material/RadioButtonUnchecked";
import SendIcon from "@mui/icons-material/SendOutlined";
import WorkHistoryIcon from "@mui/icons-material/WorkHistoryOutlined";
import { api, Expert, Solicitation } from "../../api";
import { useAuth } from "../../auth";
import { formatDateTime, frenchError } from "../../format";
import { useLoad } from "../../hooks";
import { useTokens } from "../../theme/useTokens";
import ExplainPopover from "../../components/ui/ExplainPopover";
import { SectionTitle, SkeletonCards } from "../../components/ui/Page";
import ScoreBreakdownBar from "../../components/ui/ScoreBreakdownBar";
import ScoreRing from "../../components/ui/ScoreRing";
import StatusChip from "../../components/ui/StatusChip";
import { useToast } from "../../components/ui/Toast";
import { RefuseDialog } from "../Requests";
import { useCase } from "./CaseLayout";

const initials = (name: string) => name.split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();

function ExpertCard({ expert, rank }: { expert: Expert; rank: number }) {
  const p = useTokens();
  const { weights: w, breakdown: b } = expert;
  const segments = [
    { label: "Similarité textuelle", value: b.text_score, max: w.text },
    { label: "Disponibilité", value: b.dispo_score, max: w.dispo },
    { label: "Expérience", value: b.exp_score, max: w.exp },
  ];
  return (
    <Card component="article" aria-label={`Expert ${expert.nom}`} sx={{ p: 3 }}>
      <Box sx={{ display: "flex", gap: 2.5, flexWrap: { xs: "wrap", sm: "nowrap" } }}>
        <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 1 }}>
          <ScoreRing value={expert.score} label={`Score global de ${expert.nom}`} size={96} />
          <Typography variant="caption" color="text.secondary">Score global</Typography>
        </Box>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box sx={{ display: "flex", gap: 1.5, alignItems: "center", mb: 1 }}>
            <Avatar sx={{ bgcolor: p.primarySoft, color: p.primarySoftText, fontWeight: 600 }}>{initials(expert.nom)}</Avatar>
            <Box>
              <Typography variant="overline" color="text.secondary" sx={{ display: "block" }}>Proposition n° {rank}</Typography>
              <Typography variant="h3" component="h3">{expert.nom}</Typography>
            </Box>
          </Box>
          <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", mb: 1.5 }}>
            {expert.disponibilite
              ? <Chip size="small" icon={<EventAvailableIcon sx={{ fontSize: 16 }} />} label="Disponible" sx={{ bgcolor: p.successSoft, color: p.successText, "& .MuiChip-icon": { color: "inherit" } }} />
              : <Chip size="small" icon={<EventBusyIcon sx={{ fontSize: 16 }} />} label="Indisponible" sx={{ bgcolor: p.neutralSoft, color: p.neutralText, "& .MuiChip-icon": { color: "inherit" } }} />}
            <Chip size="small" icon={<WorkHistoryIcon sx={{ fontSize: 16 }} />} label={`${expert.annees_experience} ans d'expérience`} sx={{ bgcolor: p.neutralSoft, color: p.neutralText, "& .MuiChip-icon": { color: "inherit" } }} />
          </Box>
          <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap", mb: 1.5 }} aria-label="Compétences">
            {expert.competences.map((c) => <Chip key={c} size="small" variant="outlined" label={c.replaceAll("_", " ")} />)}
          </Box>
          {expert.bio && <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{expert.bio}</Typography>}
          <ScoreBreakdownBar segments={segments} />
          <Box sx={{ mt: 1 }}>
            <ExplainPopover label="Pourquoi ce score ?" title="Pourquoi ce score ?" segments={segments} technical="score = 0,6 × similarité TF-IDF + 0,2 × disponibilité + 0,2 × min(années / 20, 1)">
              Locard compare votre description du dossier aux compétences de l'expert. À cette similarité s'ajoutent sa disponibilité
              et son expérience (20 ans valent le maximum). Le total reste un indicateur d'aide : le choix vous appartient.
            </ExplainPopover>
          </Box>
        </Box>
      </Box>
    </Card>
  );
}

function ResponseTimeline({ s }: { s: Solicitation }) {
  const p = useTokens();
  const answered = s.status !== "pending";
  const refused = s.status === "refused";
  const items = [
    { label: "Sollicité par e-mail", done: true, detail: undefined as string | undefined },
    {
      label: s.status === "pending" ? "En attente de réponse" : refused ? "A refusé" : "A accepté",
      done: answered, bad: refused, detail: s.responded_at ? formatDateTime(s.responded_at) : undefined,
    },
    { label: "Choisi pour la mission", done: s.status === "chosen", detail: undefined },
  ];
  return (
    <Box component="ol" aria-label="Avancement de la réponse" sx={{ listStyle: "none", m: 0, p: 0, display: "grid", gap: 1.25 }}>
      {items.map((it) => {
        const bad = "bad" in it && it.bad;
        return (
          <Box component="li" key={it.label} sx={{ display: "flex", gap: 1.25, alignItems: "flex-start" }}>
            {it.done
              ? <CheckCircleIcon aria-hidden="true" sx={{ fontSize: 20, color: bad ? p.danger : p.success }} />
              : s.status === "pending" && it.label.startsWith("En attente")
                ? <HourglassIcon aria-hidden="true" sx={{ fontSize: 20, color: p.warning }} />
                : <RadioButtonUncheckedIcon aria-hidden="true" sx={{ fontSize: 20, color: p.textSecondary }} />}
            <Box>
              <Typography variant="body2" sx={{ fontWeight: it.done ? 500 : 400, color: it.done ? "text.primary" : "text.secondary" }}>{it.label}</Typography>
              {it.detail && <Typography variant="caption" color="text.secondary">{it.detail}</Typography>}
            </Box>
          </Box>
        );
      })}
    </Box>
  );
}

function ProposalView({ onSent }: { onSent: () => void }) {
  const { data: c } = useCase();
  const toast = useToast();
  const experts = useLoad(() => api.experts(c.case_id), [c.case_id]);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);

  async function send() {
    if (!experts.data) return;
    setBusy(true);
    try {
      await api.solicit(c.case_id, experts.data.map((e) => e.id));
      toast.success("Les experts ont été sollicités par e-mail.");
      setConfirm(false);
      onSent();
    } catch (e) {
      toast.error(frenchError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <SectionTitle>Les 3 experts proposés</SectionTitle>
      <Typography color="text.secondary" sx={{ mb: 3, maxWidth: 720 }}>
        Locard compare votre mandat aux compétences de chaque expert, à sa disponibilité et à son expérience. Sollicitez les trois :
        ils répondent chacun de leur côté, puis vous choisissez parmi ceux qui acceptent.
      </Typography>
      {experts.error && <Alert severity="error" sx={{ mb: 2 }}>{experts.error}</Alert>}
      {experts.loading && !experts.data && <SkeletonCards count={3} height={230} />}
      <Stack spacing={2.5}>
        {experts.data?.map((e, i) => <ExpertCard key={e.id} expert={e} rank={i + 1} />)}
      </Stack>
      {experts.data && experts.data.length > 0 && (
        <Box sx={{ mt: 3 }}>
          <Button variant="contained" size="large" startIcon={<SendIcon />} onClick={() => setConfirm(true)}>Solliciter ces {experts.data.length} experts</Button>
        </Box>
      )}
      <Dialog open={confirm} onClose={busy ? undefined : () => setConfirm(false)} aria-labelledby="solicit-title" fullWidth maxWidth="sm">
        <DialogTitle id="solicit-title">Solliciter les trois experts ?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Chaque expert reçoit un e-mail. Celui qui n'a pas encore de compte reçoit une invitation personnelle pour rejoindre Locard.
            L'e-mail mentionne le type et la priorité du dossier, jamais sa description.
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setConfirm(false)} disabled={busy}>Annuler</Button>
          <Button variant="contained" onClick={send} disabled={busy}>{busy ? "Envoi…" : "Envoyer les sollicitations"}</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

function AcceptanceView({ sols, reload }: { sols: Solicitation[]; reload: () => Promise<void> }) {
  const { data: c, reload: reloadCase } = useCase();
  const toast = useToast();
  const p = useTokens();
  const [picking, setPicking] = useState<Solicitation | null>(null);
  const [busy, setBusy] = useState(false);
  const chosen = sols.find((s) => s.status === "chosen");
  const pending = sols.some((s) => s.status === "pending");
  const allRefused = sols.every((s) => s.status === "refused");

  // Answers arrive by e-mail on the experts' side: refresh quietly while some are still pending.
  useEffect(() => {
    if (!pending) return;
    const timer = window.setInterval(() => void reload(), 30_000);
    return () => window.clearInterval(timer);
  }, [pending, reload]);

  async function choose() {
    if (!picking) return;
    setBusy(true);
    try {
      await api.select(c.case_id, picking.expert_id);
      toast.success(`${picking.expert_nom} est choisi(e) pour cette mission.`);
      setPicking(null);
      await Promise.all([reload(), reloadCase()]);
    } catch (e) {
      toast.error(frenchError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <SectionTitle action={<Button size="small" onClick={() => void reload()}>Actualiser</Button>}>Réponses des experts</SectionTitle>
      {chosen && (
        <Alert severity="success" sx={{ mb: 3 }} action={<Button component={RouterLink} to={`/cases/${c.case_id}/contrat`} color="inherit" size="small">Passer au contrat</Button>}>
          {chosen.expert_nom} est chargé(e) de la mission.
        </Alert>
      )}
      {!chosen && pending && <Alert severity="info" sx={{ mb: 3 }}>Les experts ont été sollicités par e-mail. Leurs réponses apparaissent ici dès qu'elles arrivent.</Alert>}
      {allRefused && <Alert severity="warning" sx={{ mb: 3 }}>Tous les experts ont refusé ce mandat. Vous pouvez créer un nouveau mandat pour obtenir de nouvelles propositions.</Alert>}
      <Box sx={{ display: "grid", gap: 2.5, gridTemplateColumns: { xs: "1fr", lg: "repeat(3, 1fr)" } }}>
        {sols.map((s) => {
          const canChoose = s.status === "accepted" && !chosen;
          return (
            <Card key={s.id} component="article" aria-label={`Expert ${s.expert_nom}`} sx={{ p: 3, display: "flex", flexDirection: "column", gap: 2, borderColor: s.status === "chosen" ? p.primary : undefined }}>
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 1 }}>
                <Box sx={{ display: "flex", gap: 1.5, alignItems: "center", minWidth: 0 }}>
                  <Avatar sx={{ bgcolor: p.primarySoft, color: p.primarySoftText, fontWeight: 600 }}>{initials(s.expert_nom ?? "?")}</Avatar>
                  <Typography variant="h3" component="h3">{s.expert_nom}</Typography>
                </Box>
                <StatusChip status={s.status} />
              </Box>
              <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap" }}>
                {s.expert_competences.slice(0, 4).map((k) => <Chip key={k} size="small" variant="outlined" label={k.replaceAll("_", " ")} />)}
              </Box>
              <ResponseTimeline s={s} />
              {s.status === "refused" && (
                <Typography variant="body2" sx={{ bgcolor: p.dangerSoft, color: p.dangerText, p: 1.5, borderRadius: 2 }}>
                  Motif : {s.reason || "non précisé"}
                </Typography>
              )}
              {s.status === "accepted" && s.reason && <Typography variant="body2" color="text.secondary">Message : {s.reason}</Typography>}
              <Box sx={{ mt: "auto" }}>
                <Tooltip title={canChoose ? "" : chosen ? "Un expert est déjà choisi" : "Disponible quand l'expert a accepté la mission"}>
                  <span>
                    <Button variant={canChoose ? "contained" : "outlined"} fullWidth disabled={!canChoose} onClick={() => setPicking(s)}>
                      {s.status === "chosen" ? "Expert choisi" : "Choisir cet expert"}
                    </Button>
                  </span>
                </Tooltip>
              </Box>
            </Card>
          );
        })}
      </Box>
      <Dialog open={Boolean(picking)} onClose={busy ? undefined : () => setPicking(null)} aria-labelledby="choose-title" fullWidth maxWidth="sm">
        <DialogTitle id="choose-title">Choisir {picking?.expert_nom} ?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Cette décision est définitive pour ce dossier. L'expert aura accès au mandat, pourra préparer les auditions et analyser les témoignages.
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setPicking(null)} disabled={busy}>Annuler</Button>
          <Button variant="contained" onClick={choose} disabled={busy}>{busy ? "Enregistrement…" : "Confirmer le choix"}</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

/** The expert's own answer, in the case view: accept or refuse the mission. */
function ExpertAnswer({ s, reload }: { s: Solicitation; reload: () => Promise<void> }) {
  const toast = useToast();
  const { reload: reloadCase } = useCase();
  const [refusing, setRefusing] = useState(false);
  const [busy, setBusy] = useState(false);

  async function accept() {
    setBusy(true);
    try {
      await api.respond(s.id, "accepted");
      toast.success("Mission acceptée. Le mandataire peut maintenant vous choisir.");
      await Promise.all([reload(), reloadCase()]);
    } catch (e) {
      toast.error(frenchError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card sx={{ p: 3, maxWidth: 560 }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
        <Typography variant="h3" component="h2">Votre réponse</Typography>
        <StatusChip status={s.status} />
      </Box>
      <ResponseTimeline s={s} />
      {s.status === "pending" && (
        <Box sx={{ display: "flex", gap: 1.5, mt: 3 }}>
          <Button variant="contained" onClick={accept} disabled={busy}>Accepter la mission</Button>
          <Button variant="outlined" color="error" onClick={() => setRefusing(true)} disabled={busy}>Refuser</Button>
        </Box>
      )}
      {s.status === "accepted" && <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>Merci. Le mandataire n'a pas encore fait son choix.</Typography>}
      <RefuseDialog request={refusing ? s : null} onClose={() => setRefusing(false)} onDone={() => { setRefusing(false); void reload(); void reloadCase(); }} />
    </Card>
  );
}

/** Steps 2: expert proposals and the acceptance workflow (mandataire), or the expert's answer. */
export default function ExpertsStep() {
  const { data: c } = useCase();
  const { user } = useAuth();
  const sols = useLoad(() => api.solicitations(c.case_id), [c.case_id]);

  if (sols.loading && !sols.data) return <SkeletonCards count={2} height={200} />;
  if (sols.error) return <Alert severity="error">{sols.error}</Alert>;
  const list = sols.data ?? [];

  if (user?.role === "investigateur") {
    return list.length ? <ExpertAnswer s={list[0]} reload={sols.reload} /> : <Alert severity="info">Vous n'avez pas été sollicité pour ce dossier.</Alert>;
  }
  return list.length === 0 ? <ProposalView onSent={() => { void sols.reload(); }} /> : <AcceptanceView sols={list} reload={sols.reload} />;
}
