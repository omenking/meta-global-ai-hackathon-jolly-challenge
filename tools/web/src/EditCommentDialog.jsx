import { Button } from '@heroui/react';
import { useEffect, useId, useRef, useState } from 'react';

export default function EditCommentDialog({ comment, onSave, onClose }) {
  const dialogRef = useRef(null);
  const savingRef = useRef(false);
  const titleId = useId();
  const bodyId = useId();
  const labelsId = useId();
  const [body, setBody] = useState(comment.body);
  const [labels, setLabels] = useState((comment.labels || []).join(', '));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const dialog = dialogRef.current;
    const previousFocus = document.activeElement;
    dialog.showModal();
    return () => {
      dialog.close();
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, []);
  async function save(event) {
    event.preventDefault();
    if (savingRef.current || !body.trim()) return;
    savingRef.current = true;
    setBusy(true); setError('');
    try {
      await onSave({ body: body.trim(), labels });
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      savingRef.current = false;
      setBusy(false);
    }
  }
  return (
    <dialog ref={dialogRef} aria-labelledby={titleId}
      className="fixed inset-0 m-auto max-h-[90dvh] w-[calc(100%-2rem)] max-w-3xl overflow-y-auto rounded-xl border border-neutral-200 bg-white p-0 text-black shadow-2xl backdrop:bg-black/50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100"
      onCancel={(event) => { event.preventDefault(); if (!savingRef.current) onClose(); }}>
      <form onSubmit={save} className="space-y-5 p-6">
        <div className="flex items-center justify-between gap-4">
          <h2 id={titleId} className="text-xl font-semibold">Edit comment</h2>
          <Button type="button" variant="outline" isDisabled={busy} onPress={onClose}>Cancel</Button>
        </div>
        <div className="space-y-2">
          <label htmlFor={bodyId} className="block text-base font-semibold">Comment</label>
          <textarea id={bodyId} autoFocus required rows={12} value={body} disabled={busy}
            className="block min-h-64 w-full resize-y rounded-lg border border-neutral-300 bg-white p-3 text-base leading-relaxed focus:outline-2 focus:outline-blue-500 dark:border-neutral-600 dark:bg-neutral-950"
            onChange={(event) => setBody(event.target.value)} />
        </div>
        <div className="space-y-2">
          <label htmlFor={labelsId} className="block text-base font-semibold">Labels (comma-separated)</label>
          <input id={labelsId} value={labels} disabled={busy} placeholder="e.g. movement, graphics, map layout"
            className="block w-full rounded-lg border border-neutral-300 bg-white p-3 text-base focus:outline-2 focus:outline-blue-500 dark:border-neutral-600 dark:bg-neutral-950"
            onChange={(event) => setLabels(event.target.value)} />
        </div>
        {error && <p role="alert" className="whitespace-pre-wrap text-base text-red-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="submit" isPending={busy} isDisabled={busy || !body.trim()}>Save changes</Button>
        </div>
      </form>
    </dialog>
  );
}
