import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import App from "./App";

const theme = createTheme({
  palette: {
    primary: { main: "#14377B" },
    secondary: { main: "#2E86C8" },
    background: { default: "#F7F7FB" },
  },
  typography: { fontFamily: "Montserrat, Helvetica, Arial, sans-serif" },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <App />
    </ThemeProvider>
  </StrictMode>,
);
