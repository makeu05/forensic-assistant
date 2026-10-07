import { alpha, createTheme, Theme } from "@mui/material/styles";
import { brand, fonts, Mode, palette as tokens, scale } from "./tokens";

/** The Locard MUI theme, built from the tokens. `createLocardTheme("dark")` gives the dark variant. */
export function createLocardTheme(mode: Mode): Theme {
  const p = tokens[mode];
  const dark = mode === "dark";
  const focusRing = {
    outline: `2px solid ${p.focus}`,
    outlineOffset: 2,
    boxShadow: `0 0 0 5px ${alpha(brand.cyan, dark ? 0.35 : 0.3)}`,
  };

  return createTheme({
    palette: {
      mode,
      primary: { main: p.primary, contrastText: "#FFFFFF" },
      secondary: { main: brand.navy700, contrastText: "#FFFFFF" },
      success: { main: p.success },
      warning: { main: p.warning },
      error: { main: p.danger },
      info: { main: p.info },
      background: { default: p.bg, paper: p.surface },
      text: { primary: p.text, secondary: p.textSecondary },
      divider: p.border,
    },
    shape: { borderRadius: 10 },
    spacing: 8,
    typography: {
      fontFamily: fonts.sans,
      fontWeightRegular: 400,
      fontWeightMedium: 500,
      fontWeightBold: 600, // the interface only uses 400, 500 and 600
      h1: { fontSize: scale.xxl, lineHeight: 1.25, fontWeight: 600, letterSpacing: "-0.01em" },
      h2: { fontSize: scale.xl, lineHeight: 1.25, fontWeight: 600, letterSpacing: "-0.01em" },
      h3: { fontSize: scale.lg, lineHeight: 1.25, fontWeight: 600 },
      h4: { fontSize: scale.md, lineHeight: 1.25, fontWeight: 600 },
      h5: { fontSize: scale.md, lineHeight: 1.25, fontWeight: 600 },
      h6: { fontSize: scale.sm, lineHeight: 1.25, fontWeight: 600 },
      subtitle1: { fontSize: scale.md, lineHeight: 1.5, fontWeight: 500 },
      subtitle2: { fontSize: scale.sm, lineHeight: 1.5, fontWeight: 500 },
      body1: { fontSize: scale.md, lineHeight: 1.5 },
      body2: { fontSize: scale.sm, lineHeight: 1.5 },
      caption: { fontSize: scale.xs, lineHeight: 1.5 },
      overline: { fontSize: scale.xs, lineHeight: 1.5, fontWeight: 600, letterSpacing: "0.04em", textTransform: "none" },
      button: { fontSize: scale.sm, fontWeight: 500, textTransform: "none", letterSpacing: 0 },
    },
    shadows: [
      "none",
      `0 1px 2px ${alpha("#0B1F3A", dark ? 0.5 : 0.06)}`,
      `0 2px 6px ${alpha("#0B1F3A", dark ? 0.5 : 0.07)}`,
      `0 4px 12px ${alpha("#0B1F3A", dark ? 0.55 : 0.08)}`,
      ...Array(21).fill(`0 8px 24px ${alpha("#0B1F3A", dark ? 0.6 : 0.1)}`),
    ] as Theme["shadows"],
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: { backgroundColor: p.bg, color: p.text },
          "a": { color: p.primaryText },
          "code, kbd, pre, samp": { fontFamily: fonts.mono },
          ":focus-visible": focusRing,
          // Respect users who ask for less motion.
          "@media (prefers-reduced-motion: reduce)": { "*": { transitionDuration: "0.01ms !important", animationDuration: "0.01ms !important" } },
        },
      },
      // Subtitles are not headings: left as h6 they would break the heading order of every page.
      MuiTypography: { defaultProps: { variantMapping: { subtitle1: "p", subtitle2: "p", h5: "h3", h6: "h4" } } },
      MuiButtonBase: { defaultProps: { disableRipple: false }, styleOverrides: { root: { "&.Mui-focusVisible": focusRing } } },
      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: { borderRadius: 8, padding: "8px 16px", minHeight: 40, transition: "background-color 150ms ease, border-color 150ms ease, color 150ms ease" },
          sizeLarge: { minHeight: 48, fontSize: scale.md, padding: "10px 24px" },
          sizeSmall: { minHeight: 32, padding: "4px 12px" },
          textPrimary: { color: p.primaryText },
          outlinedPrimary: { color: p.primaryText, borderColor: dark ? p.border : alpha(brand.blue, 0.5) },
        },
      },
      MuiIconButton: { styleOverrides: { root: { transition: "background-color 150ms ease" } } },
      MuiCard: {
        defaultProps: { variant: "outlined" },
        styleOverrides: { root: { borderRadius: 10, borderColor: p.border, backgroundImage: "none", boxShadow: `0 1px 2px ${alpha("#0B1F3A", dark ? 0.4 : 0.04)}` } },
      },
      MuiPaper: { styleOverrides: { root: { backgroundImage: "none" }, outlined: { borderColor: p.border } } },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            borderRadius: 8, backgroundColor: p.surface, transition: "box-shadow 150ms ease",
            "& .MuiOutlinedInput-notchedOutline": { borderColor: dark ? p.border : "#C9D1DE" },
            "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: p.textSecondary },
            "&.Mui-focused": { boxShadow: `0 0 0 4px ${alpha(brand.cyan, 0.3)}` },
            "&.Mui-focused .MuiOutlinedInput-notchedOutline": { borderColor: p.focus, borderWidth: 2 },
          },
          input: { padding: "12px 14px" },
        },
      },
      MuiInputLabel: { styleOverrides: { root: { color: p.textSecondary } } },
      MuiFormHelperText: { styleOverrides: { root: { fontSize: scale.xs, marginLeft: 2 } } },
      MuiChip: { styleOverrides: { root: { fontWeight: 500, borderRadius: 8, fontSize: scale.xs }, label: { paddingInline: 10 } } },
      MuiTooltip: { styleOverrides: { tooltip: { backgroundColor: brand.navy900, fontSize: scale.xs, padding: "6px 10px" } } },
      MuiTab: { styleOverrides: { root: { minHeight: 44, fontSize: scale.sm, fontWeight: 500, "&.Mui-selected": { color: p.primaryText } } } },
      MuiTabs: { styleOverrides: { indicator: { height: 3, borderRadius: 3 } } },
      MuiLink: { defaultProps: { underline: "hover" }, styleOverrides: { root: { color: p.primaryText } } },
      MuiDialog: { styleOverrides: { paper: { borderRadius: 14 } } },
      MuiPopover: { styleOverrides: { paper: { borderRadius: 10, border: `1px solid ${p.border}` } } },
      MuiAlert: {
        styleOverrides: {
          root: { borderRadius: 10, alignItems: "center" },
          standardSuccess: { backgroundColor: p.successSoft, color: p.successText, "& .MuiAlert-icon": { color: p.success } },
          standardError: { backgroundColor: p.dangerSoft, color: p.dangerText, "& .MuiAlert-icon": { color: p.danger } },
          standardWarning: { backgroundColor: p.warningSoft, color: p.warningText, "& .MuiAlert-icon": { color: p.warning } },
          standardInfo: { backgroundColor: p.infoSoft, color: p.infoText, "& .MuiAlert-icon": { color: p.info } },
        },
      },
      MuiLinearProgress: { styleOverrides: { root: { borderRadius: 4, height: 8, backgroundColor: p.surfaceAlt } } },
      MuiSkeleton: { styleOverrides: { root: { backgroundColor: dark ? "#1C2940" : "#E8ECF3" } } },
    },
  });
}
