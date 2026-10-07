import { Navigate, Route, Routes } from "react-router-dom";
import { Box, Button, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import { RequireAuth, RequireRole } from "./auth";
import AppShell from "./layout/AppShell";
import AuditPage from "./pages/AuditPage";
import { ActivatePage, LoginPage } from "./pages/AuthPages";
import AnalysisStep from "./pages/case/AnalysisStep";
import CaseLayout from "./pages/case/CaseLayout";
import ContractStep from "./pages/case/ContractStep";
import ExpertsStep from "./pages/case/ExpertsStep";
import MandateStep from "./pages/case/MandateStep";
import PreparationStep from "./pages/case/PreparationStep";
import ReportStep from "./pages/case/ReportStep";
import Home from "./pages/Home";
import NewMandate from "./pages/NewMandate";
import OptionsPage from "./pages/OptionsPage";
import RequestsPage from "./pages/Requests";
import StyleGuide from "./pages/StyleGuide";

function NotFound() {
  return (
    <Box sx={{ textAlign: "center", py: 10 }}>
      <Typography variant="h1" component="h1" sx={{ mb: 1 }}>Page introuvable</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>L'adresse demandée n'existe pas ou a changé.</Typography>
      <Button variant="contained" component={RouterLink} to="/">Retour à l'accueil</Button>
    </Box>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/activate" element={<ActivatePage />} />
      <Route path="/style-guide" element={<StyleGuide />} />
      <Route element={<RequireAuth><AppShell /></RequireAuth>}>
        <Route index element={<Home />} />
        <Route path="cases/new" element={<RequireRole role="mandataire"><NewMandate /></RequireRole>} />
        <Route path="cases/:id" element={<CaseLayout />}>
          <Route path="mandat" element={<MandateStep />} />
          <Route path="experts" element={<ExpertsStep />} />
          <Route path="contrat" element={<ContractStep />} />
          <Route path="preparation" element={<PreparationStep />} />
          <Route path="analyse" element={<AnalysisStep />} />
          <Route path="rapport" element={<ReportStep />} />
          <Route path="audit" element={<AuditPage />} />
          <Route path="*" element={<Navigate to="mandat" replace />} />
        </Route>
        <Route path="demandes" element={<RequireRole role="investigateur"><RequestsPage /></RequireRole>} />
        <Route path="audit" element={<AuditPage />} />
        <Route path="options" element={<OptionsPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
