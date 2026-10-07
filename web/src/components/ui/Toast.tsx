import { createContext, ReactNode, useCallback, useContext, useMemo, useState } from "react";
import { Alert, Snackbar } from "@mui/material";

type Severity = "success" | "error" | "info" | "warning";
interface Toast {
  id: number;
  message: string;
  severity: Severity;
}

interface ToastApi {
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

/** Confirmation messages. Announced politely to screen readers; errors stay a little longer. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState<Toast | null>(null);
  const [open, setOpen] = useState(false);

  const show = useCallback((severity: Severity, message: string) => {
    setCurrent({ id: Date.now(), message, severity });
    setOpen(true);
  }, []);

  const api = useMemo<ToastApi>(
    () => ({ success: (m) => show("success", m), error: (m) => show("error", m), info: (m) => show("info", m) }),
    [show],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <Snackbar
        key={current?.id}
        open={open}
        autoHideDuration={current?.severity === "error" ? 8000 : 4500}
        onClose={(_, reason) => reason !== "clickaway" && setOpen(false)}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
        sx={{ mb: { xs: 8, md: 0 } }} // stay above the bottom navigation on phones
      >
        <Alert
          severity={current?.severity ?? "info"}
          onClose={() => setOpen(false)}
          role={current?.severity === "error" ? "alert" : "status"}
          sx={{ width: "100%", maxWidth: 520, boxShadow: 3, border: 1, borderColor: "divider" }}
        >
          {current?.message}
        </Alert>
      </Snackbar>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
