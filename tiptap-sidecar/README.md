# Odessa Ward Tiptap sidecar

A tiny, self-contained [Tiptap](https://tiptap.dev) rich-text editor packaged as a
standalone bundle for the Odessa Ward CRM.

The pre-existing, already-minified React app (`assets/index-CDdqaBQN.js`) can't
easily be rebuilt from source here, so instead of wiring Tiptap into that build
we ship it as a **sidecar**: a separate Vite library build that bundles its own
copy of React 18 and exposes a small global mount API. The main app loads the
bundle and calls into it to mount an editor at a DOM node of its choosing.

The two React copies (the host app's and the sidecar's) coexist safely because
the sidecar only ever renders inside the DOM nodes handed to it via `mount()`.

## Build

```bash
npm install
npm run build
```

Output is written to the repository's top-level `assets/` directory
(`emptyOutDir: false`, so existing files there are left untouched):

- `../assets/tiptap-bundle.js` — the IIFE bundle (React + Tiptap + the editor)
- `../assets/tiptap-bundle.css` — the editor + toolbar styles

Both files are committed to the `gh-pages` branch so they ship with the
deployed site.

## Runtime API

Loading `tiptap-bundle.js` defines `window.OdessaTiptap`:

```ts
window.OdessaTiptap.mount(el: HTMLElement, options): MountHandle

interface options {
  value: string;                                    // initial HTML
  onCommit: (html: string) => Promise<void> | void; // fired on blur, only if changed
  placeholder?: string;
  readOnly?: boolean;
}

interface MountHandle {
  update(options: Partial<options>): void;  // push new value/placeholder/readOnly
  destroy(): void;                          // unmount the editor
}
```

- `mount` creates a React root **inside** `el` and renders the editor.
- The editor autosaves **on blur**: `onCommit(html)` is called only when focus
  leaves the editor and the HTML differs from the last committed value.
- Use `handle.update({ value })` to swap content when navigating between records
  without recreating the editor; `handle.destroy()` to tear it down.
