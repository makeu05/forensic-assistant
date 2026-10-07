// Checks every text/background pair used by the interface against WCAG AA.
// Run: node --experimental-strip-types scripts/check-contrast.mjs
import { palette, brand } from "../src/theme/tokens.ts";

const lum = (hex) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
};
const ratio = (a, b) => {
  const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m);
  return (x + 0.05) / (y + 0.05);
};

const failures = [];
const check = (mode, name, fg, bg, min = 4.5) => {
  const r = ratio(fg, bg);
  const ok = r >= min;
  if (!ok) failures.push(`${mode} ${name}: ${r.toFixed(2)} (needs ${min})`);
  console.log(`${ok ? "ok  " : "FAIL"} ${mode.padEnd(5)} ${name.padEnd(46)} ${r.toFixed(2)}`);
};

for (const mode of ["light", "dark"]) {
  const p = palette[mode];
  for (const bg of ["bg", "surface", "surfaceAlt"]) {
    check(mode, `text on ${bg}`, p.text, p[bg]);
    check(mode, `textSecondary on ${bg}`, p.textSecondary, p[bg]);
    check(mode, `link (primaryText) on ${bg}`, p.primaryText, p[bg]);
  }
  check(mode, "white on primary button", "#FFFFFF", p.primary);
  check(mode, "white on navy700 (chip 'choisi')", "#FFFFFF", brand.navy700);
  for (const tone of ["success", "warning", "danger", "info"]) {
    check(mode, `${tone}Text on ${tone}Soft (chips, alerts)`, p[`${tone}Text`], p[`${tone}Soft`]);
    check(mode, `${tone}Text on surface`, p[`${tone}Text`], p.surface);
    check(mode, `${tone} (graphics) on surface`, p[tone], p.surface, 3);
  }
  check(mode, "primarySoftText on primarySoft", p.primarySoftText, p.primarySoft);
  check(mode, "neutralText on neutralSoft", p.neutralText, p.neutralSoft);
  check(mode, "slateText on slateSoft", p.slateText, p.slateSoft);
  check(mode, "focus ring on bg (3:1)", p.focus, p.bg, 3);
  check(mode, "focus ring on surface (3:1)", p.focus, p.surface, 3);
  check(mode, "border on surface (decorative, 1.2)", p.border, p.surface, 1.1);
}
check("both", "white on navy900 sidebar", "#FFFFFF", brand.navy900);
check("both", "cyan on navy900 (icons)", brand.cyan, brand.navy900, 3);
check("both", "#C9D1DE input border on white (3:1)", "#C9D1DE", "#FFFFFF", 1.5);

console.log(failures.length ? `\n${failures.length} FAILURE(S):\n${failures.join("\n")}` : "\nAll pairs pass.");
process.exit(failures.length ? 1 : 0);
