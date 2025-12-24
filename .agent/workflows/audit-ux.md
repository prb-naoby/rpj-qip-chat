---
description: this workflow is to audit microinteraction (UX) of current codebase
---

You are an IDE agent auditing and modifying a React + Next.js application.

This application MUST strictly follow shadcn/ui (Radix primitives) as the single source of truth for UI components, interaction states, accessibility, tooltip usage, motion, and loading behavior.

Your task is to audit the entire codebase and directly modify it to comply with the rules below.

====================================================
GLOBAL ENFORCEMENT RULES (BIDIRECTIONAL)
====================================================

1. ALL rules in this document are bidirectionally enforced.
   - If a rule requires something → ADD it.
   - If a rule forbids something → REMOVE it.
2. ALL interactive UI components MUST use shadcn/ui or Radix primitives wrapped by shadcn.
3. NO custom-built buttons, tooltips, dropdowns, dialogs, popovers, inputs, loaders, hover effects, focus styles, or cursor logic are allowed if a shadcn equivalent exists.
4. If a component does not use shadcn:
   - Replace it with the closest shadcn component.
   - Preserve behavior and props while enforcing shadcn patterns.
5. ALL loading indicators MUST be animated spinners.
   - Static icons, static SVGs, text-only loaders, or non-animated indicators are FORBIDDEN.
6. Do NOT introduce new design patterns unless required to enforce these rules.
7. Modify code directly. Do not leave TODOs, comments, or questions.

====================================================
DESIGN SYSTEM TERMINOLOGY (AUTHORITATIVE)
====================================================

- Microinteractions: small UI responses to user actions.
- Interaction States: default, hover, focus, active, disabled, loading, error, selected.
- Affordances: visual signals indicating interactivity.
- Feedback Mechanisms: tooltips, toasts, spinners, inline validation.
- Visual Cues: color, motion, opacity, shadow, cursor changes.

These concepts MUST be enforced implicitly across the codebase.

====================================================
SHADCN COMPONENT ENFORCEMENT
====================================================

Buttons
- MUST use shadcn Button
- MUST show hover, focus, active, disabled, loading states
- MUST remove any non-shadcn button implementations
- Icon-only buttons MUST have Tooltip

Inputs (Input, Textarea, Select)
- MUST use shadcn components
- MUST show focus and error states
- MUST remove custom input wrappers when redundant

Tooltip
- MUST use Radix Tooltip via shadcn
- MUST open on hover AND keyboard focus
- MUST NOT contain critical or primary content
- MUST be added OR removed according to tooltip rules below

Dialog / Modal
- MUST use shadcn Dialog
- MUST trap focus
- MUST remove non-compliant modals

Dropdown / Menu
- MUST use shadcn DropdownMenu or Popover
- MUST be keyboard navigable
- MUST remove custom dropdown logic

Tabs, Accordion, Switch, Checkbox, Radio
- MUST use shadcn equivalents
- MUST remove custom state logic where redundant
- MUST expose selected and focus states

====================================================
LOADING & ASYNC STATE RULES (BIDIRECTIONAL)
====================================================

LDR1. ALL loading states MUST use animated spinners.
LDR2. Any static loading indicator MUST be removed and replaced.
LDR3. Spinners MUST visibly animate.
LDR4. Loading spinners MUST be present for:
      - button loading
      - page loading
      - data fetching
      - async mutations
LDR5. When loading:
      - disable the triggering control
      - remove cursor-pointer
      - preserve layout stability
LDR6. Any text containing "Loading" or similar MUST be accompanied by an animated Spinner component.
      - Search pattern: grep for "Loading", "Memuat", "Mengambil" without adjacent <Spinner
      - FORBIDDEN: `<span>Loading...</span>` alone
      - REQUIRED: `<Spinner className="..." />Loading...`

====================================================
CURSOR RULES (AFFORDANCES — BIDIRECTIONAL)
====================================================

C1. Interactive elements MUST use cursor-pointer.
C2. Non-interactive elements MUST NOT use cursor-pointer.
C3. Disabled or loading elements MUST NOT use cursor-pointer.

====================================================
HOVER RULES (INTERACTION STATES — BIDIRECTIONAL)
====================================================

H1. Interactive components MUST have hover states.
H2. Hover states MUST be removed from non-interactive elements.
H3. Hover MUST NOT be the only indicator of interactivity.
H4. Hover-only interactions MUST be replaced or extended with focus equivalents.

====================================================
FOCUS RULES (ACCESSIBILITY — BIDIRECTIONAL)
====================================================

F1. All interactive components MUST expose visible focus states.
F2. Hidden or removed focus states MUST be restored or replaced.
F3. Focus MUST be visually distinct from hover.

====================================================
TOOLTIP RULES (BIDIRECTIONAL)
====================================================

TT1. Tooltips MUST be added for:
     - icon-only buttons
     - ambiguous actions
     - truncated text

TT2. Tooltips MUST be removed if:
     - visible text already explains the action
     - content is duplicated
     - used for primary or critical information
     - decorative or redundant

TT3. Tooltips MUST open on hover AND focus.
TT4. Tooltips MUST NOT block interaction.
TT5. Tooltips MUST NOT replace labels.

====================================================
BUTTON RULES (SHADCN BUTTON — BIDIRECTIONAL)
====================================================

B1. Buttons MUST show hover, focus, active, disabled, loading states.
B2. Missing states MUST be added.
B3. Redundant or incorrect states MUST be removed.
B4. Icon-only buttons MUST include Tooltip.
B5. Loading buttons MUST replace icons/text with animated spinner.

====================================================
LINK RULES (BIDIRECTIONAL)
====================================================

LN1. Navigation MUST use semantic links.
LN2. Non-navigation elements MUST NOT use link semantics.
LN3. Links MUST have hover and focus states.
LN4. Decorative links MUST be removed.

====================================================
MOTION RULES (MICROINTERACTIONS — BIDIRECTIONAL)
====================================================

M1. Motion MUST be between 100–250ms.
M2. Blocking or excessive motion MUST be removed.
M3. Motion MUST reinforce interaction.
M4. Spinner animation MUST remain active while loading.

====================================================
AUDIT WORKFLOW (NON-OPTIONAL)
====================================================

For EACH component and page:

1. Identify whether the component is interactive.
2. Enforce shadcn usage (replace or remove non-compliant components).
3. Add missing interaction states.
4. Remove forbidden or redundant interaction states.
5. Add missing feedback mechanisms.
6. Remove redundant or forbidden feedback mechanisms.
7. Audit accessibility, motion, and loading behavior.
8. Normalize behavior across similar components.

====================================================
OUTPUT REQUIREMENTS
====================================================

- Modify the codebase directly.
- Enforce ALL rules bidirectionally.
- Ensure ALL UI components rely on shadcn.
- Ensure ALL loading indicators are animated spinners.
- Do NOT explain changes.
- Do NOT skip components.
- Treat this as a full UI/UX enforcement pass.
