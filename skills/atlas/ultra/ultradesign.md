# ATLAS Ultra — Design

## Pipeline

```
1. DIAGNOSE → 2. SELECT → 3. READ → 4. SYNTHESIZE → 5. IMPLEMENT → 6. VERIFY → 7. ARTIFACT
```

### Step 1: DIAGNOSE (inline, 5 min)
Parse the brief:
- Product type (dashboard, landing page, SaaS, e-commerce, internal tool)
- Audience (developers, executives, consumers, operators)
- Density (landing, editorial, dashboard, workspace, commerce, portfolio)
- Mood (technical, cinematic, warm, luxurious, playful, austere)
- Risk (readability, trust, speed, accessibility, conversion)

### Step 2: SELECT (inline, 5 min)
- Choose primary Taste style from available style pack
- Choose 1-3 brand references from reference library
- Load ONLY the relevant style files (keep context lean)

### Step 3: READ (inline, 10 min)
- Read selected Taste style `skill.md`
- Read `components/style-recipes.md`
- Read selected brand `DESIGN.md` files
- Absorb: palette, typography, spacing, motion, component patterns

### Step 4: SYNTHESIZE (inline, 10 min)
Write a compact design contract:
```yaml
palette:
  primary: "#..."
  secondary: "#..."
  accent: "#..."
  background: "#..."
  surface: "#..."
  text: "#..."

typography:
  display: "Font Name, weight"
  body: "Font Name, weight"
  mono: "Font Name, weight"

spacing: { scale: "4px base", rhythm: "8px" }
layout: { max-width: "1200px", grid: "12-col" }
motion: { level: "subtle|moderate|expressive", easing: "cubic-bezier(...)" }
radius: { sm: "2px", md: "4px", lg: "8px" }
shadows: { card: "...", elevated: "..." }

components:
  button: { variants: [...], states: [...] }
  card: { variants: [...] }
  input: { variants: [...] }

do: ["...", "..."]
dont: ["...", "..."]
```

### Step 5: IMPLEMENT (inline or subagent, 20-60 min)
- Build the UI using the design contract
- For complex pages: decompose into components, implement each
- Use existing component library as base, apply design contract on top
- Follow framework patterns (React/Next.js/Vue/etc.)

### Step 6: VERIFY (inline, 10 min)
Check implementation bar:
- [ ] Responsive layout (mobile + desktop)
- [ ] No text overflow or incoherent overlap
- [ ] Clear hierarchy and readable contrast
- [ ] Expected controls and states exist
- [ ] Brand/style visible in actual pixels
- [ ] No generic AI aesthetics (decorative orbs, weak gradients)
- [ ] Accessibility: keyboard nav, screen reader, contrast ratios

### Step 7: ARTIFACT (inline, 5 min)
- Save design contract to `{ARTIFACT_DIR}/ATLAS-ULTRA-DESIGN-{slug}-contract.md` (resolved per SKILL.md Saving Results)
- Save implementation notes to `{ARTIFACT_DIR}/ATLAS-ULTRA-DESIGN-{slug}.md` (resolved per SKILL.md Saving Results)

## Subagent Prompt (for complex implementations)

```
You are a design implementation subagent.

Design contract: {CONTRACT_YAML}

Your ONLY task — implement this component:
{COMPONENT_DESCRIPTION}

Rules:
1. Follow the design contract exactly (palette, typography, spacing, motion)
2. Use the framework's component patterns
3. Implement responsive layout
4. Include all states (default, hover, active, disabled, loading, error)
5. Write to {WORKSPACE}/{COMPONENT_FILE}
6. Return: 3-5 line summary of what was built
```

## ATLAS-native

ATLAS WebUI uses React + Tailwind. Design contracts should reference the existing component library. Implementation subagents write to the WebUI source tree. Tag parallel component implementations `[actor-ok]`.
