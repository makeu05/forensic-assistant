import { FormEvent, ReactNode, useState } from "react";
import { Link as RouterLink, Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { Alert, Box, Button, Card, IconButton, InputAdornment, Link, Tab, Tabs, TextField, Typography } from "@mui/material";
import FingerprintIcon from "@mui/icons-material/Fingerprint";
import FactCheckIcon from "@mui/icons-material/FactCheckOutlined";
import HistoryIcon from "@mui/icons-material/HistoryOutlined";
import TagIcon from "@mui/icons-material/TagOutlined";
import VisibilityIcon from "@mui/icons-material/VisibilityOutlined";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOffOutlined";
import { api } from "../api";
import { useAuth } from "../auth";
import { frenchError } from "../format";
import { useLoad } from "../hooks";
import { brand } from "../theme/tokens";
import { SkeletonCards } from "../components/ui/Page";

const EMAIL_RX = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/;
const MIN_PASSWORD = 12;

function AuthLayout({ children }: { children: ReactNode }) {
  const points = [
    { icon: <TagIcon />, text: "Une empreinte SHA-256 pour chaque document produit" },
    { icon: <HistoryIcon />, text: "Un journal d'audit à chaîne de hachage : toute altération est détectée" },
    { icon: <FactCheckIcon />, text: "Des résultats toujours expliqués, jamais une boîte noire" },
  ];
  return (
    <Box sx={{ minHeight: "100vh", display: "grid", gridTemplateColumns: { xs: "1fr", md: "minmax(360px, 5fr) 7fr" }, bgcolor: "background.default" }}>
      <Box component="header" sx={{ bgcolor: brand.navy900, color: "#FFFFFF", p: { xs: 3, md: 6 }, display: "flex", flexDirection: "column", justifyContent: "space-between", gap: 4 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <FingerprintIcon aria-hidden="true" sx={{ color: brand.cyan, fontSize: 36 }} />
          <Typography sx={{ fontSize: 24, fontWeight: 600 }}>Locard</Typography>
        </Box>
        <Box sx={{ display: { xs: "none", md: "block" } }}>
          <Typography variant="h1" component="p" sx={{ color: "#FFFFFF", mb: 2 }}>Tout contact laisse une trace.</Typography>
          <Typography sx={{ color: "#C7D3E5", mb: 4, maxWidth: 440 }}>
            L'assistant d'investigation numérique qui guide le mandataire et l'expert, du mandat au rapport, avec une traçabilité vérifiable.
          </Typography>
          <Box component="ul" sx={{ listStyle: "none", m: 0, p: 0, display: "grid", gap: 2 }}>
            {points.map((p) => (
              <Box component="li" key={p.text} sx={{ display: "flex", gap: 1.5, alignItems: "flex-start" }}>
                <Box aria-hidden="true" sx={{ color: brand.cyan, display: "flex", mt: 0.25 }}>{p.icon}</Box>
                <Typography sx={{ color: "#FFFFFF" }}>{p.text}</Typography>
              </Box>
            ))}
          </Box>
        </Box>
        <Typography variant="caption" sx={{ color: "#C7D3E5", display: { xs: "none", md: "block" } }}>
          Principe d'échange de Locard : tout contact entre deux éléments laisse une trace.
        </Typography>
      </Box>
      <Box component="main" id="main" sx={{ display: "grid", placeItems: "center", p: { xs: 2, md: 6 } }}>
        <Card sx={{ width: "100%", maxWidth: 460, p: { xs: 3, sm: 4 } }}>{children}</Card>
      </Box>
    </Box>
  );
}

function PasswordField({ label, value, onChange, error, helper, autoComplete, id }: {
  label: string; value: string; onChange: (v: string) => void; error?: boolean; helper?: string; autoComplete: string; id: string;
}) {
  const [shown, setShown] = useState(false);
  return (
    <TextField
      id={id} label={label} type={shown ? "text" : "password"} value={value} onChange={(e) => onChange(e.target.value)}
      error={error} helperText={helper} autoComplete={autoComplete} fullWidth required
      InputProps={{
        endAdornment: (
          <InputAdornment position="end">
            <IconButton onClick={() => setShown((s) => !s)} aria-label={shown ? "Masquer le mot de passe" : "Afficher le mot de passe"} edge="end">
              {shown ? <VisibilityOffIcon /> : <VisibilityIcon />}
            </IconButton>
          </InputAdornment>
        ),
      }}
    />
  );
}

export function LoginPage() {
  const { login, register, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";
  const [tab, setTab] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (user) return <Navigate to={from} replace />;

  const emailError = touched && !EMAIL_RX.test(email);
  const passwordError = touched && tab === "register" && password.length < MIN_PASSWORD;
  const nameError = touched && tab === "register" && name.trim().length < 2;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    setError("");
    if (!EMAIL_RX.test(email) || !password || (tab === "register" && (password.length < MIN_PASSWORD || name.trim().length < 2))) return;
    setBusy(true);
    try {
      if (tab === "login") await login(email.trim(), password);
      else await register(email.trim(), name.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(frenchError(err, "login"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <Typography variant="h2" component="h1" sx={{ mb: 0.5 }}>{tab === "login" ? "Connexion" : "Créer un compte mandataire"}</Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        {tab === "login" ? "Accédez à vos dossiers d'investigation." : "Pour émettre des mandats d'investigation (juge, dirigeant, particulier)."}
      </Typography>
      <Tabs value={tab} onChange={(_, v) => { setTab(v); setError(""); setTouched(false); }} variant="fullWidth" sx={{ mb: 3 }} aria-label="Connexion ou inscription">
        <Tab value="login" label="Connexion" />
        <Tab value="register" label="Créer un compte" />
      </Tabs>
      <Box component="form" onSubmit={submit} noValidate sx={{ display: "grid", gap: 2.5 }}>
        {error && <Alert severity="error" role="alert">{error}</Alert>}
        {tab === "register" && (
          <TextField id="name" label="Nom complet" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" fullWidth required
            error={nameError} helperText={nameError ? "Indiquez votre nom (2 caractères minimum)." : "Tel qu'il apparaîtra sur les mandats."} />
        )}
        <TextField id="email" label="Adresse e-mail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" fullWidth required
          error={emailError} helperText={emailError ? "Saisissez une adresse valide, par exemple nom@organisation.fr." : " "} />
        <PasswordField
          id="password" label="Mot de passe" value={password} onChange={setPassword} autoComplete={tab === "login" ? "current-password" : "new-password"}
          error={passwordError} helper={tab === "register" ? `${MIN_PASSWORD} caractères minimum (${password.length}/${MIN_PASSWORD}). Une phrase longue est idéale.` : undefined}
        />
        <Button type="submit" variant="contained" size="large" disabled={busy} fullWidth>
          {busy ? "Un instant…" : tab === "login" ? "Se connecter" : "Créer mon compte"}
        </Button>
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 3 }}>
        Vous êtes expert ? Votre compte se crée depuis le lien d'invitation reçu par e-mail.
      </Typography>
      <Typography variant="body2" sx={{ mt: 1 }}>
        <Link component={RouterLink} to="/style-guide">Guide de style</Link>
      </Typography>
    </AuthLayout>
  );
}

export function ActivatePage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const invitation = useLoad(() => api.invitation(token), [token]);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const mismatch = touched && password !== confirm;
  const tooShort = touched && password.length < MIN_PASSWORD;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    setError("");
    if (password.length < MIN_PASSWORD || password !== confirm) return;
    setBusy(true);
    try {
      signIn(await api.activate(token, password, name.trim() || undefined));
      navigate("/", { replace: true });
    } catch (err) {
      setError(frenchError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <Typography variant="h2" component="h1" sx={{ mb: 0.5 }}>Activer votre compte expert</Typography>
      {invitation.loading && <SkeletonCards count={2} height={56} />}
      {invitation.error && (
        <>
          <Alert severity="error" sx={{ my: 2 }}>{token ? "Ce lien d'invitation est invalide, déjà utilisé ou expiré." : "Aucun lien d'invitation fourni."}</Alert>
          <Typography variant="body2">Demandez au mandataire de vous solliciter à nouveau pour recevoir un nouveau lien, ou <Link component={RouterLink} to="/login">connectez-vous</Link>.</Typography>
        </>
      )}
      {invitation.data && (
        <>
          <Typography color="text.secondary" sx={{ mb: 3 }}>
            Bonjour {invitation.data.expert_name}. Choisissez un mot de passe pour accéder aux demandes de mission.
            Votre identifiant sera <strong>{invitation.data.email}</strong>.
          </Typography>
          <Box component="form" onSubmit={submit} noValidate sx={{ display: "grid", gap: 2.5 }}>
            {error && <Alert severity="error" role="alert">{error}</Alert>}
            <TextField id="display-name" label="Nom affiché (facultatif)" value={name} onChange={(e) => setName(e.target.value)} placeholder={invitation.data.expert_name} fullWidth />
            <PasswordField id="new-password" label="Mot de passe" value={password} onChange={setPassword} autoComplete="new-password"
              error={tooShort} helper={`${MIN_PASSWORD} caractères minimum (${password.length}/${MIN_PASSWORD}).`} />
            <PasswordField id="confirm-password" label="Confirmer le mot de passe" value={confirm} onChange={setConfirm} autoComplete="new-password"
              error={mismatch} helper={mismatch ? "Les deux mots de passe ne correspondent pas." : undefined} />
            <Button type="submit" variant="contained" size="large" disabled={busy} fullWidth>
              {busy ? "Création du compte…" : "Activer mon compte"}
            </Button>
          </Box>
        </>
      )}
    </AuthLayout>
  );
}
