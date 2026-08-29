# Deploy pipeline

## Serving path

The app is served entirely from `Daveagentai/odessa-ward` **`gh-pages` branch** by a Cloudflare Worker named `odessa-ward`.

- `wrangler.jsonc` at repo root declares the Worker with `assets.directory = "."` — the entire branch is served as static assets. No Cloudflare Pages, no separate `dist/`.
- Live URL: **https://odessa-ward.dhoussian.workers.dev/**
- There is **no CI/CD**. Nothing in this repo auto-builds or auto-deploys. Deploys happen by pushing directly to gh-pages, at which point Cloudflare serves the new files.

## Deploying (real workflow)

Because we have no buildable source tree (see `DESIGN_DOCUMENT.md` § "Source situation"), a "deploy" today means:

1. **Patch the compiled bundle in place.** Regex-patch `assets/index-CDdqaBQN.js` for the change we want. Rules:
   - Single unique anchor before replacement.
   - `(` `{` `[` balance preserved — baseline is `(-1, 0, 1)`.
   - `node --check assets/index-CDdqaBQN.js` passes.
   - Report the size delta.
2. **Bump the cache buster.** Edit `index.html`'s `<script>` tag:
   ```html
   <script type="module" crossorigin src="./assets/index-CDdqaBQN.js?v=YYYY-MM-DD-N"></script>
   ```
   Increment `N` for every patch on the same day. This forces both Cloudflare's edge cache AND browsers to fetch the new bundle without a hard refresh.
3. **Update `docs/bundle-patches.md`.** New chronological entry: offset(s), before/after, motivation.
4. **Update `docs/bundle-identifiers.md`** if we identified new minified names in the process.
5. **Commit + push to gh-pages** with `api_credentials=["github"]`:
   ```bash
   cd /home/user/workspace/odessa-ward-app
   git add -A
   git commit -m "<short imperative description>"
   git push origin gh-pages
   ```
6. **Verify live.** Load the URL in a fresh tab. Cache buster should mean no hard refresh is needed.

## Why the cache buster matters

The bundle filename `assets/index-CDdqaBQN.js` **never changes** across in-place patches — Vite would normally hash-rename it on rebuild, but we're not rebuilding, we're editing. Both:

- **Cloudflare edge:** the Worker caches the asset URL indefinitely.
- **Browsers:** treat the same filename as cached forever.

Without the query-string cache buster, users see the OLD bundle after a normal refresh and have to hit Cmd+Shift+R (hard refresh) to see changes. The cache-buster convention (`?v=YYYY-MM-DD-N`, bumped every patch) fixes this at the source.

**Convention:** `N` starts at `1` each day and increments per patch. E.g. two patches on 2026-08-29 → `?v=2026-08-29-1`, `?v=2026-08-29-2`. Three patches → `?v=2026-08-29-3`. Simple.

## The other repo (`Daveagentai/ward-crm`)

Dave's standing rule is "commit code to both repos so they stay in sync." For this project that rule is currently vacuous: `Daveagentai/ward-crm` is 5+ months stale and does not represent what's deployed. Until we reverse-engineer the bundle back into a buildable source tree, there is no source to commit to that repo. See `DESIGN_DOCUMENT.md` § "Source situation".

When the source tree is reconstructed:
- `Daveagentai/ward-crm` should be the source-of-truth repo (`main` branch).
- The build pipeline should push compiled output to `Daveagentai/odessa-ward` `gh-pages`.
- At that point, "commit to both repos" becomes real again.

## Wrangler / manual deploy

Not currently needed — pushes to gh-pages ARE the deploy. If we ever need to force a Worker redeploy:

```bash
cd /home/user/workspace/odessa-ward-app
wrangler deploy
```

Requires the user's Cloudflare account credentials, which live in their environment, not in this sandbox.

## Emergency rollback

Bundle is versioned in git. To roll back:

```bash
cd /home/user/workspace/odessa-ward-app
git log --oneline assets/index-CDdqaBQN.js | head -20      # find the commit before the bad one
git checkout <good-sha> -- assets/index-CDdqaBQN.js
# bump the cache buster in index.html to a NEW value so users refresh past the bad one
git add -A && git commit -m "Rollback bundle to <good-sha>"
git push origin gh-pages
```

## Last verified

- 2026-08-29 — documented as part of the design-doc consolidation.
