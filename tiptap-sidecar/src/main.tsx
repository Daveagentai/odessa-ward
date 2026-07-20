import { createRoot, type Root } from 'react-dom/client';
import { TiptapField } from './TiptapField';
import './styles.css';

interface MountOptions {
  value: string;
  onCommit: (html: string) => Promise<void> | void;
  placeholder?: string;
  readOnly?: boolean;
}

interface MountHandle {
  update(options: Partial<MountOptions>): void;
  destroy(): void;
}

/**
 * Mount a Tiptap rich-text editor inside `el`.
 *
 * Creates a React root INSIDE the given element (the sidecar ships its own
 * React 18, independent of the host app's React) and renders <TiptapField>.
 * The returned handle lets the host push a new `value` (or other options) when
 * navigating between records without tearing down and recreating the editor.
 */
function mount(el: HTMLElement, opts: MountOptions): MountHandle {
  const root: Root = createRoot(el);
  let current: MountOptions = { ...opts };

  const render = () => {
    root.render(
      <TiptapField
        value={current.value}
        onCommit={current.onCommit}
        placeholder={current.placeholder}
        readOnly={current.readOnly}
      />
    );
  };

  render();

  return {
    update(next: Partial<MountOptions>) {
      current = { ...current, ...next };
      render();
    },
    destroy() {
      root.unmount();
    },
  };
}

(window as any).OdessaTiptap = { mount };

export { mount };
