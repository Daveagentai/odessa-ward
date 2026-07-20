import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Builds src/main.tsx as a single self-contained IIFE bundle that exposes
// window.OdessaTiptap.mount(root, options). React is intentionally bundled in
// (not externalized) so the sidecar does not depend on the host app's React.
export default defineConfig({
  plugins: [react()],
  // React's CJS build branches on process.env.NODE_ENV. In library mode Vite
  // does not always replace it, so define it explicitly to get the production
  // (small, warning-free) React build and avoid "process is not defined".
  define: {
    'process.env.NODE_ENV': JSON.stringify('production'),
  },
  build: {
    lib: {
      entry: 'src/main.tsx',
      name: 'OdessaTiptap',
      formats: ['iife'],
      fileName: () => 'tiptap-bundle.js',
    },
    outDir: '../assets',
    emptyOutDir: false,
    rollupOptions: {
      output: {
        assetFileNames: 'tiptap-bundle[extname]',
        globals: {},
      },
    },
    cssCodeSplit: false,
    minify: true,
  },
});
