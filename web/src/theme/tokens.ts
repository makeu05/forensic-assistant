/**
 * Locard design tokens.
 *
 * The brand colours come from the design brief. Where a brief colour cannot reach WCAG AA (4.5:1)
 * as text on its tinted background, a `...Text` variant is defined and used for text only, while
 * the brief colour stays for icons, bars and borders (3:1 is enough for graphics):
 *   warning #B7791F on #FEF3C7 = 3.3:1  ->  warningText #8A5A00 = 5.3:1
 *   success #12805C on #E7F6EF = 4.4:1  ->  successText #0E6B4C = 5.9:1
 *   info    #0B7FA8 on #E3F3F9 = 4.0:1  ->  infoText    #086585 = 5.8:1
 * Contrast is checked by a script (web/scripts/check-contrast.mjs), not by eye.
 */
export type Mode = "light" | "dark";

export const brand = {
  navy900: "#0B1F3A",
  navy700: "#17335C",
  blue: "#1D5FD1",
  cyan: "#00C2FF",
} as const;

export const palette = {
  light: {
    bg: "#F6F8FB",
    surface: "#FFFFFF",
    surfaceAlt: "#F0F3F8",
    border: "#E3E8EF",
    text: "#101828",
    textSecondary: "#475467",
    primary: "#1D5FD1",
    primaryText: "#1D5FD1", // links and text buttons
    primarySoft: "#E8F0FD",
    primarySoftText: "#1747A8",
    success: "#12805C", successSoft: "#E7F6EF", successText: "#0E6B4C",
    warning: "#B7791F", warningSoft: "#FEF3C7", warningText: "#8A5A00",
    danger: "#C0392B", dangerSoft: "#FBEAE8", dangerText: "#A62F23",
    info: "#0B7FA8", infoSoft: "#E3F3F9", infoText: "#086585",
    neutralSoft: "#EEF1F6", neutralText: "#475467",
    slateSoft: "#E9EEF5", slateText: "#3D5069",
    focus: "#1D5FD1", // outline colour; the cyan glow is added around it
  },
  dark: {
    bg: "#0B1220",
    surface: "#121C2E",
    surfaceAlt: "#18243A",
    border: "#243349",
    text: "#E7ECF3",
    textSecondary: "#9FB0C7",
    primary: "#2F6FE0",
    primaryText: "#7FB0FF",
    primarySoft: "#14284D",
    primarySoftText: "#A9C8FF",
    success: "#3DB88A", successSoft: "#0F2B22", successText: "#7FDDB8",
    warning: "#E0A93B", warningSoft: "#332706", warningText: "#F2CC7A",
    danger: "#E5695B", dangerSoft: "#341512", dangerText: "#F4A39A",
    info: "#4DB6DC", infoSoft: "#0D2A36", infoText: "#8FD3EC",
    neutralSoft: "#1C2940", neutralText: "#B5C2D6",
    slateSoft: "#1C2940", slateText: "#B5C2D6",
    focus: "#00C2FF",
  },
} as const;

export type Palette = (typeof palette)[Mode];

/** Entity colours for the PV highlighter. Each also has its own underline style, so colour is never the only cue. */
export const entityStyles = (p: Palette) => ({
  personne: { bg: p.primarySoft, fg: p.primarySoftText, line: "solid", label: "Personne" },
  lieu: { bg: p.successSoft, fg: p.successText, line: "dashed", label: "Lieu" },
  date: { bg: p.warningSoft, fg: p.warningText, line: "dotted", label: "Date" },
  montant: { bg: p.dangerSoft, fg: p.dangerText, line: "double", label: "Montant" },
  heure: { bg: p.infoSoft, fg: p.infoText, line: "wavy", label: "Heure" },
});

export const fonts = {
  sans: '"Inter", "Helvetica Neue", Arial, sans-serif',
  mono: '"JetBrains Mono", "SFMono-Regular", Consolas, monospace',
};

/** Type scale from the brief: 12 / 14 / 16 / 20 / 24 / 32. */
export const scale = { xs: 12, sm: 14, md: 16, lg: 20, xl: 24, xxl: 32 } as const;
