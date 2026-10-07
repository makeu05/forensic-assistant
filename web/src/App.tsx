import { useState } from "react";
import { AppBar, Box, Container, Toolbar, Typography } from "@mui/material";
import Dashboard from "./components/Dashboard";
import CaseForm from "./components/CaseForm";
import CaseDetail from "./components/CaseDetail";

type View = { name: "dashboard" } | { name: "new" } | { name: "case"; id: string };

export default function App() {
  const [view, setView] = useState<View>({ name: "dashboard" });

  return (
    <Box>
      <AppBar position="static" elevation={0}>
        <Toolbar>
          <Typography
            variant="h6"
            sx={{ fontWeight: 800, cursor: "pointer" }}
            onClick={() => setView({ name: "dashboard" })}
          >
            Assistant d'investigation numerique
          </Typography>
          <Typography variant="caption" sx={{ ml: 2, opacity: 0.8 }}>
            Espace mandataire
          </Typography>
        </Toolbar>
      </AppBar>
      <Container maxWidth="md" sx={{ py: 4 }}>
        {view.name === "dashboard" && (
          <Dashboard onNew={() => setView({ name: "new" })} onOpen={(id) => setView({ name: "case", id })} />
        )}
        {view.name === "new" && (
          <CaseForm
            onCancel={() => setView({ name: "dashboard" })}
            onCreated={(id) => setView({ name: "case", id })}
          />
        )}
        {view.name === "case" && <CaseDetail id={view.id} onBack={() => setView({ name: "dashboard" })} />}
      </Container>
    </Box>
  );
}
