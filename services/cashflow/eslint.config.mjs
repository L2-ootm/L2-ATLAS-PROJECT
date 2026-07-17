import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // The vendored cashflow repositories cross untyped SQLite/Supabase row
      // boundaries. TypeScript still checks every consumer, while these narrow
      // exceptions avoid pretending those external payloads are fully typed.
      "@typescript-eslint/no-explicit-any": "off",
      // React 19 compiler advisory rules flag established modal hydration and
      // Recharts callback patterns that are valid in this non-compiled app.
      "react-hooks/immutability": "off",
      "react-hooks/purity": "off",
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/static-components": "off",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
