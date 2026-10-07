import { Alert, Box, Card, Chip, Stack, Typography } from "@mui/material";
import ScheduleIcon from "@mui/icons-material/ScheduleOutlined";
import { api, Hypothesis, PlanStep } from "../../api";
import { ACTION_TITLE } from "../../format";
import { useLoad } from "../../hooks";
import { useTokens } from "../../theme/useTokens";
import ExplainPopover from "../../components/ui/ExplainPopover";
import { SectionTitle, SkeletonCards } from "../../components/ui/Page";
import { useCase } from "./CaseLayout";

function HypothesisCard({ h }: { h: Hypothesis }) {
  const p = useTokens();
  const fromPv = h.origin === "incoherence";
  return (
    <Card component="article" sx={{ p: 2.5, display: "flex", flexDirection: "column", gap: 1.25 }}>
      <Chip size="small" label={fromPv ? "Déduite des incohérences" : "Déduite du type de dossier"}
        sx={{ alignSelf: "flex-start", bgcolor: fromPv ? p.warningSoft : p.primarySoft, color: fromPv ? p.warningText : p.primarySoftText }} />
      <Typography variant="h4" component="h3">{h.label}</Typography>
      <Typography variant="body2" color="text.secondary">{h.basis}</Typography>
      <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap" }} aria-label="Actions à mener">
        {h.actions.map((a) => <Chip key={a} size="small" variant="outlined" label={ACTION_TITLE[a] ?? a} />)}
      </Box>
      {h.pv_references.length > 0 && (
        <Typography variant="caption" color="text.secondary">PV concernés : {h.pv_references.join(", ")}</Typography>
      )}
    </Card>
  );
}

function PlanTimeline({ plan, hypotheses }: { plan: PlanStep[]; hypotheses: Hypothesis[] }) {
  const p = useTokens();
  const labelOf = (id: string) => hypotheses.find((h) => h.id === id)?.label ?? id;
  return (
    <Box component="ol" aria-label="Plan d'actions forensiques" sx={{ listStyle: "none", m: 0, p: 0 }}>
      {plan.map((step, i) => (
        <Box component="li" key={step.action} sx={{ display: "grid", gridTemplateColumns: "40px 1fr", columnGap: 2 }}>
          <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <Box aria-hidden="true" sx={{ width: 36, height: 36, borderRadius: "50%", display: "grid", placeItems: "center", bgcolor: p.primary, color: "#FFFFFF", fontWeight: 600 }}>
              {step.priority}
            </Box>
            {i < plan.length - 1 && <Box aria-hidden="true" sx={{ flex: 1, width: 2, bgcolor: p.border, my: 0.5 }} />}
          </Box>
          <Card sx={{ p: 2.5, mb: 2.5 }}>
            <Box sx={{ display: "flex", justifyContent: "space-between", gap: 1, flexWrap: "wrap", mb: 0.5 }}>
              <Typography variant="h4" component="h3"><Box component="span" sx={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>Priorité {step.priority} : </Box>{step.label}</Typography>
              <Chip size="small" icon={<ScheduleIcon sx={{ fontSize: 16 }} />} label={step.duree_estimee} sx={{ bgcolor: p.neutralSoft, color: p.neutralText, "& .MuiChip-icon": { color: "inherit" } }} />
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>{step.description}</Typography>
            <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap", mb: 1.5 }} aria-label="Outils">
              {step.outils.map((o) => <Chip key={o} size="small" label={o} sx={{ bgcolor: p.primarySoft, color: p.primarySoftText }} />)}
            </Box>
            <ExplainPopover title={`Pourquoi la priorité ${step.priority} ?`} technical={`hypothèses : ${step.justified_by.join(", ")}`}>
              {step.why} Elle répond à : {step.justified_by.map(labelOf).join(" ; ")}.
              À nombre égal d'hypothèses servies, l'ordre suit celui dans lequel les hypothèses citent leurs actions.
            </ExplainPopover>
          </Card>
        </Box>
      ))}
    </Box>
  );
}

/** Screen 8: hypotheses as cards, then the ordered forensic actions with tools and estimated duration. */
export default function MethodTab() {
  const { data: c } = useCase();
  const m = useLoad(() => api.methodology(c.case_id), [c.case_id]);

  if (m.loading && !m.data) return <SkeletonCards count={3} height={130} />;
  if (m.error) return <Alert severity="error">{m.error}</Alert>;
  const data = m.data;
  if (!data) return null;

  return (
    <>
      <Alert severity="info" sx={{ mb: 3 }}>
        Les hypothèses sont des pistes à vérifier, pas des conclusions. Elles découlent du type de dossier et des incohérences détectées dans les PV.
      </Alert>
      <SectionTitle>Hypothèses d'investigation</SectionTitle>
      <Box sx={{ display: "grid", gap: 2.5, gridTemplateColumns: { xs: "1fr", md: "repeat(2, 1fr)", xl: "repeat(3, 1fr)" }, mb: 5 }}>
        {data.hypotheses.map((h) => <HypothesisCard key={h.id} h={h} />)}
      </Box>

      <SectionTitle action={<Typography color="text.secondary">Durée totale estimée : <strong>{data.duree_totale_estimee}</strong></Typography>}>
        Plan d'actions forensiques
      </SectionTitle>
      <Stack sx={{ maxWidth: 820 }}>
        {data.plan.length === 0
          ? <Alert severity="info">Aucune action à planifier pour le moment.</Alert>
          : <PlanTimeline plan={data.plan} hypotheses={data.hypotheses} />}
      </Stack>
    </>
  );
}
