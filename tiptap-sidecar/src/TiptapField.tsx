import { useCallback, useEffect, useRef, useState } from 'react';
import type { FocusEvent, ReactNode } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';

// Small local replacement for the `cn`/clsx helper from the host app: joins
// truthy class strings with spaces.
function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}

export interface TiptapFieldProps {
  value: string; // HTML string
  onCommit: (html: string) => Promise<void> | void; // called on blur if changed
  placeholder?: string;
  readOnly?: boolean;
}

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

// Inline SVG icons (lucide paths) so we don't pull in lucide-react and bloat
// the bundle. All use stroke:currentColor so they follow the button color.
function Icon({ children }: { children: ReactNode }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

const BoldIcon = (
  <Icon>
    <path d="M14 12a4 4 0 0 0 0-8H6v8" />
    <path d="M15 20a4 4 0 0 0 0-8H6v8Z" />
  </Icon>
);

const ItalicIcon = (
  <Icon>
    <line x1="19" x2="10" y1="4" y2="4" />
    <line x1="14" x2="5" y1="20" y2="20" />
    <line x1="15" x2="9" y1="4" y2="20" />
  </Icon>
);

const BulletListIcon = (
  <Icon>
    <line x1="8" x2="21" y1="6" y2="6" />
    <line x1="8" x2="21" y1="12" y2="12" />
    <line x1="8" x2="21" y1="18" y2="18" />
    <line x1="3" x2="3.01" y1="6" y2="6" />
    <line x1="3" x2="3.01" y1="12" y2="12" />
    <line x1="3" x2="3.01" y1="18" y2="18" />
  </Icon>
);

const OrderedListIcon = (
  <Icon>
    <line x1="10" x2="21" y1="6" y2="6" />
    <line x1="10" x2="21" y1="12" y2="12" />
    <line x1="10" x2="21" y1="18" y2="18" />
    <path d="M4 6h1v4" />
    <path d="M4 10h2" />
    <path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1" />
  </Icon>
);

const HorizontalRuleIcon = (
  <Icon>
    <path d="M5 12h14" />
  </Icon>
);

function ToolbarButton({
  onClick,
  active,
  title,
  children,
}: {
  onClick: () => void;
  active?: boolean;
  title: string;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      // Prevent the editor from losing focus (which would trigger a blur/commit)
      // when a toolbar button is pressed.
      onMouseDown={(e) => {
        e.preventDefault();
        onClick();
      }}
      title={title}
      aria-label={title}
      aria-pressed={active}
      className={cx('tiptap-tb-btn', active && 'is-active')}
    >
      {children}
    </button>
  );
}

export function TiptapField({
  value,
  onCommit,
  placeholder = 'Click to add a description...',
  readOnly = false,
}: TiptapFieldProps) {
  const [status, setStatus] = useState<SaveStatus>('idle');

  // Last HTML we successfully committed via onCommit, and the latest HTML in the
  // editor. onCommit only fires on blur when these differ.
  const lastCommittedRef = useRef<string>(value || '');
  const currentHtmlRef = useRef<string>(value || '');

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        // Disable extensions we don't need to keep the bundle small.
        codeBlock: false,
        blockquote: false,
        heading: { levels: [1, 2, 3] },
      }),
      Placeholder.configure({
        placeholder,
        emptyEditorClass: 'is-editor-empty',
      }),
    ],
    content: value || '',
    editable: !readOnly,
    onUpdate: ({ editor }) => {
      // Return empty string instead of a bare <p></p> so we don't store noise.
      currentHtmlRef.current = editor.isEmpty ? '' : editor.getHTML();
    },
    editorProps: {
      attributes: {
        class: 'tiptap-content focus:outline-none',
      },
    },
  });

  // Keep editor content in sync when `value` changes externally (e.g. the host
  // app navigates to a different calling). Only update when not focused and the
  // content actually differs, to avoid resetting the cursor mid-edit.
  useEffect(() => {
    if (!editor) return;
    if (editor.isFocused) return;
    const incoming = value || '';
    const current = editor.isEmpty ? '' : editor.getHTML();
    if (incoming !== current) {
      editor.commands.setContent(incoming, { emitUpdate: false });
    }
    lastCommittedRef.current = incoming;
    currentHtmlRef.current = incoming;
  }, [value, editor]);

  // Reflect readOnly changes pushed via the mount handle's update().
  useEffect(() => {
    if (!editor) return;
    editor.setEditable(!readOnly);
  }, [editor, readOnly]);

  // "Saved" indicator fades away after 1.5s.
  useEffect(() => {
    if (status !== 'saved') return;
    const t = setTimeout(() => setStatus('idle'), 1500);
    return () => clearTimeout(t);
  }, [status]);

  const commit = useCallback(async () => {
    const html = currentHtmlRef.current;
    if (html === lastCommittedRef.current) return;
    try {
      setStatus('saving');
      await onCommit(html);
      lastCommittedRef.current = html;
      setStatus('saved');
    } catch {
      setStatus('error');
    }
  }, [onCommit]);

  const handleBlur = useCallback(
    (e: FocusEvent<HTMLDivElement>) => {
      // Ignore focus moving between elements inside the field (e.g. to a
      // toolbar button); only commit when focus truly leaves the container.
      if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
      void commit();
    },
    [commit]
  );

  if (!editor) return null;

  return (
    <div
      className={cx('tiptap-field', readOnly && 'is-readonly')}
      onBlur={handleBlur}
    >
      <div className="tiptap-status" aria-live="polite">
        {status === 'saving' && <span className="tiptap-status-saving">Saving…</span>}
        {status === 'saved' && <span className="tiptap-status-saved">Saved</span>}
        {status === 'error' && (
          <button
            type="button"
            className="tiptap-status-error"
            onMouseDown={(e) => {
              e.preventDefault();
              void commit();
            }}
          >
            Save failed — retry
          </button>
        )}
      </div>

      {!readOnly && (
        <div className="tiptap-toolbar">
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBold().run()}
            active={editor.isActive('bold')}
            title="Bold (Ctrl+B)"
          >
            {BoldIcon}
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleItalic().run()}
            active={editor.isActive('italic')}
            title="Italic (Ctrl+I)"
          >
            {ItalicIcon}
          </ToolbarButton>
          <span className="tiptap-tb-sep" />
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            active={editor.isActive('bulletList')}
            title="Bullet list"
          >
            {BulletListIcon}
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            active={editor.isActive('orderedList')}
            title="Numbered list"
          >
            {OrderedListIcon}
          </ToolbarButton>
          <span className="tiptap-tb-sep" />
          <ToolbarButton
            onClick={() => editor.chain().focus().setHorizontalRule().run()}
            title="Divider"
          >
            {HorizontalRuleIcon}
          </ToolbarButton>
        </div>
      )}

      <div className="tiptap-body">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}
