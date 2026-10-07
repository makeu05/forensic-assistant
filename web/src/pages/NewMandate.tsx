import { ReactNode, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert, Autocomplete, Box, Button, Card, Chip, Divider, Step, StepLabel, Stepper, TextField, Typography,
} from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircleOutline";
import RadioButtonUncheckedIcon from "@mui/icons-material/RadioButtonUnchecked";
import { api, CaseType, Priority } from "../api";
import { useAuth } from "../auth";
import { CASE_TYPE_HELP, CASE_TYPE_LABEL, frenchError, PRIORITY_LABEL } from "../format";
import { useTokens } from "../theme/useTokens";
import { PageHeader } from "../components/ui/Page";
import { useToast } from "../components/ui/Toast";
import { CASE_ICON } from "./Home";

const STEPS = ["Type de dossier", "Description et priorité", "Mandataire"];
const MAX_DESCRIPTION = 2000;
const MIN_DESCRIPTION = 10;

const EXAMPLES: Record<CaseType, string> = {
  fraude_bancaire: "Virements suspects de 50 000 euros vers un compte étranger entre le 1er et le 10 octobre 2025. Analyse des journaux bancaires et des témoignages du service comptable.",
  intrusion_reseau: "Connexions SSH suspectes depuis une adresse interne à 03h42, avec environ 2 Go de données sortantes. Identification du compte utilisé et des systèmes touchés.",
  malware: "Un rançongiciel a chiffré le serveur de fichiers de la société. Reconstitution de la chronologie d'infection à partir de la pièce jointe ouverte par un collaborateur.",
};

const PRIORITY_HELP: Record<Priority, string> = {
  basse: "Pas d'urgence particulière.",
  moyenne: "À traiter dans les prochaines semaines.",
  haute: "Urgence judiciaire ou risque pour les preuves.",
};

const FUNCTIONS = ["Juge d'instruction", "Procureur", "Avocat", "Dirigeant d'entreprise", "Responsable de la sécurité", "Particulier"];

function ChoiceCard({ checked, onSelect, name, value, title, text, icon }: {
  checked: boolean; onSelect: () => void; name: string; value: string; title: string; text: string; icon?: ReactNode;
}) {
  const p = useTokens();
  return (
    <Box
      component="label"
      sx={{
        display: "flex", gap: 1.5, alignItems: "flex-start", p: 2, borderRadius: 2.5, cursor: "pointer", bgcolor: "background.paper",
        border: `2px solid ${checked ? p.primary : p.border}`, boxShadow: checked ? `0 0 0 3px ${p.primarySoft}` : "none",
        transition: "border-color 150ms ease, box-shadow 150ms ease", "&:hover": { borderColor: checked ? p.primary : p.textSecondary },
        "&:has(input:focus-visible)": { outline: `2px solid ${p.focus}`, outlineOffset: 2 },
      }}
    >
      <Box component="input" type="radio" name={name} value={value} checked={checked} onChange={onSelect}
        sx={{ position: "absolute", opacity: 0, width: 1, height: 1 }} />
      {icon && <Box aria-hidden="true" sx={{ color: checked ? p.primary : p.textSecondary, display: "flex", mt: 0.25 }}>{icon}</Box>}
      <Box>
        <Typography sx={{ fontWeight: 600 }}>{title}</Typography>
        <Typography variant="body2" color="text.secondary">{text}</Typography>
      </Box>
    </Box>
  );
}

function SummaryRow({ label, value }: { label: string; value?: string }) {
  const done = Boolean(value);
  return (
    <Box sx={{ display: "flex", gap: 1.5, alignItems: "flex-start" }}>
      {done ? <CheckCircleIcon color="success" fontSize="small" aria-hidden="true" /> : <RadioButtonUncheckedIcon fontSize="small" sx={{ color: "text.secondary" }} aria-hidden="true" />}
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="caption" color="text.secondary">{label}</Typography>
        <Typography variant="body2" sx={{ fontWeight: done ? 500 : 400, color: done ? "text.primary" : "text.secondary", wordBreak: "break-word" }}>
          {value || "À renseigner"}
        </Typography>
      </Box>
    </Box>
  );
}

export default function NewMandate() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [step, setStep] = useState(0);
  const [type, setType] = useState<CaseType | null>(null);
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<Priority>("moyenne");
  const [nom, setNom] = useState(user?.display_name ?? "");
  const [fonction, setFonction] = useState("");
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const descriptionError = description.trim().length < MIN_DESCRIPTION;
  const valid = [Boolean(type), !descriptionError, nom.trim().length > 0 && fonction.trim().length > 0];

  function next() {
    setTouched(true);
    if (!valid[step]) return;
    setTouched(false);
    setStep(step + 1);
  }

  async function create() {
    setTouched(true);
    if (!valid.every(Boolean) || !type) return;
    setBusy(true);
    setError("");
    try {
      const { case_id } = await api.createCase({ case_type: type, description: description.trim(), priority, mandataire: { nom: nom.trim(), fonction: fonction.trim() } });
      toast.success("Mandat créé. Voici les experts proposés.");
      navigate(`/cases/${case_id}/experts`);
    } catch (e) {
      setError(frenchError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Nouveau mandat" subtitle="Trois étapes. Vous pourrez relire le récapitulatif avant de créer le dossier." />
      <Stepper activeStep={step} alternativeLabel sx={{ mb: 4 }}>
        {STEPS.map((label, i) => <Step key={label} completed={i < step}><StepLabel>{label}</StepLabel></Step>)}
      </Stepper>

      <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", md: "minmax(0, 3fr) minmax(280px, 2fr)" }, alignItems: "start" }}>
        <Card sx={{ p: { xs: 2.5, sm: 4 }, order: { xs: 2, md: 1 } }}>
          {error && <Alert severity="error" sx={{ mb: 3 }} role="alert">{error}</Alert>}

          {step === 0 && (
            <Box component="fieldset" sx={{ border: 0, p: 0, m: 0 }}>
              <Typography component="legend" variant="h3" sx={{ mb: 0.5 }}>Quel type d'investigation ?</Typography>
              <Typography color="text.secondary" sx={{ mb: 2.5 }}>Ce choix oriente la sélection des experts et les questions d'audition.</Typography>
              <Box sx={{ display: "grid", gap: 1.5 }}>
                {(Object.keys(CASE_TYPE_LABEL) as CaseType[]).map((t) => {
                  const Icon = CASE_ICON[t];
                  return <ChoiceCard key={t} name="type" value={t} checked={type === t} onSelect={() => setType(t)} title={CASE_TYPE_LABEL[t]} text={CASE_TYPE_HELP[t]} icon={<Icon />} />;
                })}
              </Box>
              {touched && !type && <Typography role="alert" variant="body2" color="error" sx={{ mt: 1.5 }}>Choisissez un type de dossier pour continuer.</Typography>}
            </Box>
          )}

          {step === 1 && (
            <Box sx={{ display: "grid", gap: 3 }}>
              <Box>
                <Typography variant="h3" component="h2" sx={{ mb: 0.5 }}>Décrivez les faits</Typography>
                <Typography color="text.secondary" sx={{ mb: 2 }}>La période, les sommes ou systèmes concernés et ce que l'expert doit établir.</Typography>
                <TextField
                  label="Description du mandat" value={description} onChange={(e) => setDescription(e.target.value.slice(0, MAX_DESCRIPTION))}
                  multiline minRows={5} fullWidth required error={touched && descriptionError}
                  helperText={touched && descriptionError ? `Décrivez le dossier en ${MIN_DESCRIPTION} caractères au moins.` : `${description.length} / ${MAX_DESCRIPTION} caractères`}
                />
                {type && (
                  <Button size="small" onClick={() => setDescription(EXAMPLES[type])} sx={{ mt: 1 }}>Insérer un exemple de description</Button>
                )}
              </Box>
              <Box component="fieldset" sx={{ border: 0, p: 0, m: 0 }}>
                <Typography component="legend" variant="h4" sx={{ mb: 1.5 }}>Priorité</Typography>
                <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" } }}>
                  {(Object.keys(PRIORITY_LABEL) as Priority[]).map((pr) => (
                    <ChoiceCard key={pr} name="priority" value={pr} checked={priority === pr} onSelect={() => setPriority(pr)} title={PRIORITY_LABEL[pr]} text={PRIORITY_HELP[pr]} />
                  ))}
                </Box>
              </Box>
            </Box>
          )}

          {step === 2 && (
            <Box sx={{ display: "grid", gap: 2.5 }}>
              <Box>
                <Typography variant="h3" component="h2" sx={{ mb: 0.5 }}>Qui émet le mandat ?</Typography>
                <Typography color="text.secondary">Ces informations figureront sur le mandat PDF.</Typography>
              </Box>
              <TextField label="Nom et prénom" value={nom} onChange={(e) => setNom(e.target.value)} fullWidth required error={touched && !nom.trim()} helperText={touched && !nom.trim() ? "Indiquez le nom du mandataire." : " "} autoComplete="name" />
              <Autocomplete
                freeSolo options={FUNCTIONS} inputValue={fonction} onInputChange={(_, v) => setFonction(v)}
                renderInput={(params) => (
                  <TextField {...params} label="Fonction" required error={touched && !fonction.trim()} helperText={touched && !fonction.trim() ? "Indiquez votre fonction." : "Choisissez dans la liste ou saisissez la vôtre."} />
                )}
              />
            </Box>
          )}

          <Divider sx={{ my: 3 }} />
          <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
            <Button onClick={() => { setTouched(false); setStep(step - 1); }} disabled={step === 0 || busy}>Retour</Button>
            {step < 2 ? (
              <Button variant="contained" onClick={next}>Continuer</Button>
            ) : (
              <Button variant="contained" size="large" onClick={create} disabled={busy}>{busy ? "Création…" : "Créer le mandat"}</Button>
            )}
          </Box>
        </Card>

        <Card component="aside" aria-label="Récapitulatif du mandat" sx={{ p: 3, position: { md: "sticky" }, top: { md: 88 }, order: { xs: 1, md: 2 } }}>
          <Typography variant="h4" component="h2" sx={{ mb: 2 }}>Récapitulatif</Typography>
          <Box sx={{ display: "grid", gap: 2 }}>
            <SummaryRow label="Type de dossier" value={type ? CASE_TYPE_LABEL[type] : undefined} />
            <SummaryRow label="Description" value={description.trim() ? (description.length > 140 ? `${description.slice(0, 140)}…` : description) : undefined} />
            <Box sx={{ display: "flex", gap: 1.5, alignItems: "center" }}>
              <CheckCircleIcon color="success" fontSize="small" aria-hidden="true" />
              <Box><Typography variant="caption" color="text.secondary" component="div">Priorité</Typography><Chip size="small" label={PRIORITY_LABEL[priority]} /></Box>
            </Box>
            <SummaryRow label="Mandataire" value={nom.trim() && fonction.trim() ? `${nom.trim()}, ${fonction.trim()}` : undefined} />
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 2 }}>
            Après création, Locard propose trois experts, calculés à partir de votre description.
          </Typography>
        </Card>
      </Box>
    </>
  );
}
