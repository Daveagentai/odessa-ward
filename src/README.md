# Recovered application source

`recovered-app.js` is the readable, formatted recovery of the deployed JavaScript
bundle at commit 2433d52. It includes bundled dependencies and retains original
minified symbol names; it is not the original React/TypeScript source.

Edit this source, not `assets/index-CDdqaBQN.js`. Run `npm ci` and `npm run build`
to regenerate the deployed asset. Bump the script query version in `index.html`
for each deployment. The initial source recovery is a formatting-only baseline.

The existing public application has privileged-key exposure documented in the
project architecture notes. Recovery does not resolve that separate security
issue; do not add credentials or expand privileged operations here.
