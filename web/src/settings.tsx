import { createContext, ReactNode, useContext, useMemo } from "react";
import { CssBaseline, ThemeProvider } from "@mui/material";
import { useStored } from "./hooks";
import { createLocardTheme } from "./theme/theme";
import type { Mode } from "./theme/tokens";

interface Settings {
  mode: Mode;
  setMode: (mode: Mode) => void;
  /** RGPD option: show people's names as "Personne A", "Personne B" in PV views and reports. */
  pseudonymize: boolean;
  setPseudonymize: (value: boolean) => void;
}

const SettingsContext = createContext<Settings | null>(null);

export function SettingsProvider({ children }: { children: ReactNode }) {
  // Light is the default; the choice is remembered on this device.
  const [mode, setMode] = useStored<Mode>("locard.mode", "light");
  const [pseudonymize, setPseudonymize] = useStored<boolean>("locard.pseudonymize", false);
  const theme = useMemo(() => createLocardTheme(mode), [mode]);
  const value = useMemo(() => ({ mode, setMode, pseudonymize, setPseudonymize }), [mode, setMode, pseudonymize, setPseudonymize]);
  return (
    <SettingsContext.Provider value={value}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </SettingsContext.Provider>
  );
}

export function useSettings(): Settings {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error("useSettings must be used inside SettingsProvider");
  return ctx;
}
