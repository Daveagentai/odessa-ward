# Odessa Ward CRM — Documentation

Durable knowledge about this deployment. Update these files whenever we learn something we'd otherwise re-discover next session.

## Files

- **[bundle-identifiers.md](./bundle-identifiers.md)** — Map of minified identifiers in `assets/index-CDdqaBQN.js` to their real names. Update every time we identify a new one.
- **[bundle-patches.md](./bundle-patches.md)** — History of every hand-patch applied to the compiled bundle. What we changed, where, and why. So we know what to reapply if a rebuild ever happens.
- **[architecture.md](./architecture.md)** — How the app is structured: routes, tables, data flow, deploy pipeline.
- **[status-model.md](./status-model.md)** — The status model: household `activity_status` vs member `lcr_status`. What values mean, who writes them, when they're rendered.
- **[deploy.md](./deploy.md)** — How the deploy pipeline works. Cloudflare Workers via wrangler + GitHub push.
- **[importer.md](./importer.md)** — LCR importer behavior, invariants, and edge cases. Complements the `lcr-import` user skill.

## Why this exists

The React/TypeScript source for this app is gone (see `capture-learnings` skill — the "App source-of-truth rule"). All development has happened via ephemeral Perplexity sandbox sessions that generated source, compiled it, pushed the bundle to `Daveagentai/odessa-ward` gh-pages, and let the sandbox evaporate. `Daveagentai/ward-crm` (the intended source repo) is 5+ months stale and does not represent what's deployed.

Until we reverse-engineer the bundle back into a real source tree, every change to app behavior happens by:

1. Reading `assets/index-CDdqaBQN.js` to locate the minified code that renders/handles the behavior.
2. Regex-patching that file.
3. Committing the patched file back to `Daveagentai/odessa-ward` gh-pages.

That is slow, error-prone, and repeatedly re-derives the same "what does `VO` mean?" question. **This directory is the memory of what we've already figured out.**

## Rules for updating

- **Every time we grep for a minified identifier and identify it, add it to `bundle-identifiers.md`.**
- **Every time we patch the bundle, add an entry to `bundle-patches.md` with offset, before/after, and reasoning.**
- **Every time we discover a schema fact, trigger behavior, or invariant, put it in the relevant file.**
- **Every time the bundle is rebuilt (new `index-*.js` hash), verify offsets. Names may shift.**

## Last verified

- 2026-08-29 — docs directory created during the household-status-simplification work.
