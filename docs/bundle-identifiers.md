# Bundle identifiers — `assets/index-CDdqaBQN.js`

This app is deployed as a compiled/minified React bundle. The original TypeScript source is lost (see `capture-learnings` skill — the "App source-of-truth rule"). Until we reverse-engineer the bundle back into `Daveagentai/ward-crm`, patches happen directly on the minified bundle.

**Every time we grep or patch, we have to figure out what minified identifiers like `VO`, `eA`, `Fe` mean. That's slow and error-prone.** This file is the durable map.

Update this whenever we identify a new identifier. Group by concern.

## How to read this

- Bundle offsets are for `assets/index-CDdqaBQN.js` at commit HEAD of `Daveagentai/odessa-ward` `gh-pages`.
- **These offsets change every time the bundle is rebuilt.** Names may too (Vite/rollup mangler is not stable across builds). Treat offsets as a starting hint; always verify with a grep of the surrounding context (a nearby test-id or a unique string literal).
- `Ce` is the lucide-react icon factory. Anything declared as `Ce("IconName", [...])` is a lucide icon component.

## Status option arrays (13 hardcoded values, all identical today)

All four contain the same list: `["Active", "Active - Ready to Serve", "Active - Serving", "Active - Hold", "Less-Active", "Not Active - Contact OK", "Not Active - Unknown", "Do NOT Contact", "Do NOT Contact - Hostile", "Moved Out", "Deceased", "Name Removal Requested", "Check for Moved Out"]`

| ID  | Offset  | Used at | What it drives | Notes |
|-----|---------|---------|----------------|-------|
| `VO` | 633446 | 635490 | Household detail — activity_status **edit dropdown** (Select) | `data-testid="select-activity-status"` — quick pill. |
| `XO` | 682171 | 688560 | Household detail — inline field **edit dropdown** (Select) | Inside `function uh({householdId, field, label, icon, ...})`. Same test-id. |
| `eA` | 694136 | 699539 | Search Households — **filter checkbox group** (checkboxes) | Inside `function re(...)`. `data-testid="activity-status-checkboxes"`. |
| `oA` | ~705370 | 711089 | Search Members — **filter checkbox group** (checkboxes) | Inside `function X(...)`. Same visual pattern as `eA`. |

**Which arrays get shortened when we simplify to 7 household values:**

- `VO`, `XO` → shorten to the 7 clerk-facing household values: `["Active", "Less Active", "Not Active", "Not Active - Unknown", "Do NOT Contact", "Do NOT Contact - Hostile", "Moved Out"]`
- `eA`, `oA` → these are FILTERS. Filters need to match whatever statuses actually exist. After the DB migration, `households.activity_status` only has 8 values (7 above + `Check for Moved Out`). Filter list should be all 8 values. **Do NOT shorten these to 7 — clerks still need to filter for the importer-set "Check for Moved Out" state.**

## Color map for household status pills

`tA` @ ~694400 — object mapping status → Tailwind classes. Referenced from `eA`'s declaration line. Keys are the 13 historical values; after our migration, some keys become unreachable but harmless (dead branches in a map lookup).

## shadcn / Radix primitives

| ID | Component | Notes |
|----|-----------|-------|
| `we` | `Button` | `variant`, `size`, `asChild` props. `data-testid` common. |
| `Ie` | `Input` | Plain shadcn input. |
| `ge` | `Card` | Rounded, bordered wrapper. |
| `xe` | `CardContent` | `p-6 pt-0` inner padding. |
| `Be` | `Select` (root) | Radix Select root. Signature: `n.jsxs(Be, { value, onValueChange, children: [<trigger>, <content>] })`. |
| `$e` | `SelectTrigger` | The clickable trigger button. Signature: `n.jsx($e, { className, "data-testid": ..., children: n.jsx(ze, {}) })`. |
| `ze` | `SelectValue` | Renders the currently-selected value or placeholder. Confirmed by usage pattern `n.jsx(ze, {})` inside `$e`. |
| `Fe` | `SelectContent` | Radix Select's popover content. |
| `de` | `SelectItem` | Radix Select's option. Rendered as `<de value={x}>{x}</de>` in the JSX. |
| `on` | `Checkbox` | Radix Checkbox. Used in `eA`/`oA` filter lists. |

## Utility functions

| ID | What it does |
|----|--------------|
| `He` | `clsx`/`tailwind-merge` combined — takes strings, returns className string. |
| `Ce` | lucide-react `createLucideIcon` factory. Every `const X = Ce("IconName", [...])` is a lucide icon. |
| `Zt` | shadcn `useToast` hook. Returns `{ toast, dismiss, ...state }`. |

## Lucide icons (partial list)

| ID | Icon |
|----|------|
| `Di` | `Phone` |
| `hc` | `Mail` |
| `yo` | `MapPin` |
| `kN` | `LogOut` |
| `ny` | `ChevronRight` |
| `sn` | `ChevronUp` |
| `vN` | `Church` |

## React Query

| ID | What it is |
|----|-----------|
| `bt` | `useMutation` — signature matches: `function bt(e, t) { const r = vr(); const [a] = g.useState(() => new Qj(r, e)); ...` |
| `vr` | `useQueryClient` — inferred from usage in `bt`. Not directly declared with that name in the bundle. |
| `Ue` | `useQuery` — confirmed usage `Ue({ queryKey: [...], queryFn: async () => {...} })`. |
| `Ne` | `supabase` client — confirmed usage `Ne.from("members").select("*")...`. |

## Router (wouter, based on API shape)

| ID | What it is |
|----|-----------|
| `Dr` | `useLocation` — returns `[location, setLocation]` tuple. Used as `const [, e] = Dr()`. |

## Auth / Profile

| ID | What it is |
|----|-----------|
| `_t` | `useAuth` (assumed) — returns `{ profile: ..., user: ... }`. Used as `const { profile: t, user } = _t()`. Actual `_t` declaration @788330 is a shadowed local — the export `_t` is somewhere else. |

## Application components (as of 2026-08-29 bundle CDdqaBQN)

These are `wouter` route components. They're minified names that will re-mangle on rebuild, but they're the current identifiers to grep for.

| ID | Route | Purpose | Notes |
|----|-------|---------|-------|
| `sP` | `/directory` | Member Directory | 895 KB main bundle; renders list of members with status pill (we patched to read `lcr_status`). |
| `YO` | `/directory/:id` | Member Detail | Big — 43 KB. Renders name, badges, contact info, callings, tasks, visits, ministering assignments. We inject the Member Status Card here. |
| `ZO` | `/household/:id` | Household Detail | Renders household activity_status via `QO` sub-component. |
| `QO` | (sub-component) | Household activity_status quick pill | Signature: `function QO({householdId:e, currentStatus:t})`. Contains a Select using `Be`/`$e`/`ze`/`Fe`/`de` primitives. |
| `uh` | (sub-component) | Household inline field editor | Signature: `function uh({householdId, field, label, icon, ...})`. Renders `XO` dropdown when the field is activity_status. |
| `nA` | `/search-household` | Search Households | Uses `eA` filter checkbox group. |
| `lA` | `/search-members` | Search Members | Uses `oA` filter checkbox group. |
| `hO` | `/new-visit` | Log a visit | |
| `FO` | `/tasks` | Task list | |
| `qO` | `/profile` | Current user profile | |
| `cA` | `/admin` | User Management | Bishopric-only. |
| `GO` | (sub-component) | Member notes editor | Signature: `function GO({memberId:e, initialNotes:t})`. |

## Utility maps observed

| ID | What it is | Notes |
|----|-----------|-------|
| `rP` | Household activity_status → Tailwind classes | Keyed on **display strings** ("Active", "Less-Active", ...), NOT enum keys. If we render `members.lcr_status` (enum key) through this map, we must translate first. |
| `tA` | Similar/dup color map @694400 | See declaration around `eA` decl. |
| `HO`, `WO`, `aA` | Role-permission arrays | Contain values like `["bishop", "leadership", "rs_president", "eq_president", ...]`. Used to gate access. |

## JSX runtime

| ID | What it is |
|----|-----------|
| `n` | JSX runtime module — `n.jsx(...)`, `n.jsxs(...)`, `n.Fragment`. |
| `g` | React itself — `g.useState`, `g.useEffect`, `g.forwardRef`, `g.memo`, `g.useCallback`. |
| `Sn` | `flushSync` from react-dom. |

## How to verify an identifier when in doubt

The mangler is deterministic per build but names shift when new code is added. To confirm what `XYZ` is:

1. Find its declaration: `grep -oE '(const|function|let|var)\s+XYZ\b[^;]{0,200}'`.
2. Look for a nearby unique string literal (test-id, aria-label, placeholder). E.g. `data-testid="select-activity-status"` was our hook for finding `VO` and `XO`.
3. Look at what it's called with — arg names in destructured props survive minification in some cases (e.g. `function uh({householdId, field, label, icon, ...})`).

## Last verified

- **2026-08-29** — initial capture during the household-status-simplification bundle patch. Bundle: `assets/index-CDdqaBQN.js` (895,270 bytes, hash `CDdqaBQN`). VO/XO/eA/oA + core primitives mapped.
