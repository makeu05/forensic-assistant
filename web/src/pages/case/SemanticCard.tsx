import { useEffect, useState } from "react";
import { Alert, Box, Button, Card, Chip, LinearProgress, Stack, Typography } from "@mui/material";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesomeOutlined";
import { api, SemanticSuggestion } from "../../api";
import { formatDateTime, frenchError, percent } from "../../format";
import { useLoad } from "../../hooks";
import { useTokens } from "../../theme/useTokens";
import ExplainPopover from "../../components/ui/ExplainPopover";
import { useToast } from "../../components/ui/Toast";
import Excerpt from "./Excerpt";

const POLL_MS = 2500;

/** The model's scores saturate near 1, so never show 100 %: it would read as a certainty the model does not have. */
const score = (value: number) => `${Math.min(99, Math.floor(value * 100))} %`;

/** One pair of sentences the model finds contradictory. Styled apart from the rule-based findings: it is a lead, not a result. */
function SuggestionItem({ s }: { s: SemanticSuggestion }) {
  const p = useTokens();
  return (
    <Card component="article" variant="outlined" sx={{ p: 2.5, borderLeft: `4px solid ${p.info}` }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 1, flexWrap: "wrap", mb: 1.5 }}>
        <Chip size="small" label="Suggestion automatique" sx={{ bgcolor: p.infoSoft, color: p.infoText, fontWeight: 600 }} />
        <Typography variant="body2" color="text.secondary">Score du modèle : {score(s.score)}</Typography>
      </Box>
      <Box sx={{ display: "flex", gap: 1.5, flexDirection: { xs: "column", sm: "row" }, mb: 1.5 }}>
        <Excerpt pv={s.pv_a} text={s.sentence_a} />
        <Excerpt pv={s.pv_b} text={s.sentence_b} />
      </Box>
      <ExplainPopover title="Pourquoi cette suggestion ?" technical={`mots communs : ${s.shared.join(", ")}`}>
        Un modèle de langue a lu ces deux phrases et leur donne un score de {score(s.score)} pour la contradiction. Ce score classe
        les suggestions entre elles, mais ce n'est pas une probabilité fiable. Le modèle ne distingue pas toujours une vraie
        contradiction d'une différence d'heure, de personne ou d'objet : relisez les deux PV avant d'en tirer une conclusion.
      </ExplainPopover>
    </Card>
  );
}

/**
 * Contradictions suggested by a language model, kept apart from the rule-based inconsistencies and outside the
 * coherence score. Hidden when the server has no model, or when the case has fewer than two statements.
 */
export default function SemanticCard({ caseId, pseudonymize, pvCount }: { caseId: string; pseudonymize: boolean; pvCount: number }) {
  const toast = useToast();
  const result = useLoad(() => api.semanticSuggestions(caseId, pseudonymize), [caseId, pseudonymize, pvCount]);
  const [starting, setStarting] = useState(false);
  const { data, reload } = result;
  const running = data?.status === "running";

  // While the background run works, look again every few seconds; `data` changes at each look, which re-arms the timer.
  useEffect(() => {
    if (!running) return;
    const timer = setTimeout(() => void reload(), POLL_MS);
    return () => clearTimeout(timer);
  }, [running, data, reload]);

  async function start() {
    setStarting(true);
    try {
      await api.runSemantic(caseId);
      toast.info("Analyse du modèle lancée.");
      await reload();
    } catch (e) {
      toast.error(frenchError(e));
    } finally {
      setStarting(false);
    }
  }

  if (!data || !data.available || pvCount < 2) return null;

  const found = data.suggestions.length;
  return (
    <Card component="section" aria-labelledby="semantic-title" sx={{ p: { xs: 2.5, sm: 3 }, mt: 3 }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 2, flexWrap: "wrap", mb: 2 }}>
        <Box sx={{ maxWidth: 720 }}>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
            <AutoAwesomeIcon fontSize="small" color="primary" aria-hidden />
            <Typography id="semantic-title" variant="h3" component="h2">Suggestions du modèle</Typography>
          </Stack>
          <Typography variant="body2" color="text.secondary">{data.disclaimer}</Typography>
        </Box>
        <Button variant="outlined" onClick={start} disabled={running || starting}>
          {data.status === "none" ? "Lancer l'analyse" : "Relancer l'analyse"}
        </Button>
      </Box>

      <Box role="status" aria-live="polite">
        {data.status === "none" && (
          <Typography variant="body2">
            Aucune analyse lancée pour ce dossier. Le modèle compare chaque phrase d'un PV aux phrases proches des autres PV.
          </Typography>
        )}
        {running && (
          <Box>
            <LinearProgress sx={{ mb: 1 }} />
            <Typography variant="body2">Le modèle compare les déclarations. Cela peut prendre de quelques secondes à quelques minutes.</Typography>
          </Box>
        )}
        {data.status === "failed" && <Alert severity="error">L'analyse a échoué : {data.error}</Alert>}
        {data.stale && data.status !== "none" && !running && (
          <Alert severity="warning" sx={{ mt: data.status === "failed" ? 1.5 : 0 }}>
            Les PV ont changé depuis cette analyse : ces suggestions peuvent être périmées. Relancez l'analyse.
          </Alert>
        )}
        {data.status === "done" && (
          <Typography variant="body2" color="text.secondary" sx={{ my: 1.5 }}>
            {found === 0
              ? `Le modèle ne signale rien au seuil de ${percent(data.min_score ?? 0)}`
              : `${found} suggestion(s)`}
            {" "}· {data.stats.candidates ?? 0} paires de phrases examinées{data.stats.seconds != null ? ` en ${data.stats.seconds} s` : ""}
            {data.finished_at ? ` · analyse du ${formatDateTime(data.finished_at)}` : ""}
          </Typography>
        )}
      </Box>

      {data.status === "done" && found > 0 && (
        <Stack spacing={2}>{data.suggestions.map((s, i) => <SuggestionItem key={i} s={s} />)}</Stack>
      )}
    </Card>
  );
}
