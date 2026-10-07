import { useState } from "react";
import { AppBar, Box, Container, Toolbar, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material";
import Dashboard from "./components/Dashboard";
import CaseForm from "./components/CaseForm";
import CaseDetail from "./components/CaseDetail";
import InvestigatorDashboard from "./components/InvestigatorDashboard";
import MissionDetail from "./components/MissionDetail";

type Role = "mandataire" | "investigateur";
type View = { name: "dashboard" } | { name: "new" } | { name: "case"; id: string };

const ROLE_LABEL: Record<Role, string> = { mandataire: "Mandataire", investigateur: "Investigateur" };

export default function App() {
  // No authentication yet (JWT is planned): the role switch stands in for it.
  const [role, setRole] = useState<Role>("mandataire");
  const [view, setView] = useState<View>({ name: "dashboard" });
  const home = () => setView({ name: "dashboard" });

  return (
    <Box>
      <AppBar position="static" elevation={0}>
        <Toolbar sx={{ gap: 2, flexWrap: "wrap" }}>
          <Typography variant="h6" sx={{ fontWeight: 800, cursor: "pointer" }} onClick={home}>
            Locard
          </Typography>
          <Typography variant="caption" sx={{ opacity: 0.8, flexGrow: 1 }}>
            Espace {ROLE_LABEL[role].toLowerCase()}
          </Typography>
          <ToggleButtonGroup
            exclusive size="small" value={role} aria-label="Role"
            onChange={(_, next: Role | null) => {
              if (next) {
                setRole(next);
                home();
              }
            }}
            sx={{ bgcolor: "rgba(255,255,255,0.12)", "& .MuiToggleButton-root": { color: "white", px: 2 },
              "& .Mui-selected": { bgcolor: "rgba(255,255,255,0.3) !important" } }}
          >
            <ToggleButton value="mandataire">Mandataire</ToggleButton>
            <ToggleButton value="investigateur">Investigateur</ToggleButton>
          </ToggleButtonGroup>
        </Toolbar>
      </AppBar>
      <Container maxWidth="md" sx={{ py: 4 }}>
        {role === "mandataire" && (
          <>
            {view.name === "dashboard" && (
              <Dashboard onNew={() => setView({ name: "new" })} onOpen={(id) => setView({ name: "case", id })} />
            )}
            {view.name === "new" && (
              <CaseForm onCancel={home} onCreated={(id) => setView({ name: "case", id })} />
            )}
            {view.name === "case" && <CaseDetail id={view.id} onBack={home} />}
          </>
        )}
        {role === "investigateur" && (
          <>
            {view.name === "case" ? (
              <MissionDetail id={view.id} onBack={home} />
            ) : (
              <InvestigatorDashboard onOpen={(id) => setView({ name: "case", id })} />
            )}
          </>
        )}
      </Container>
    </Box>
  );
}
