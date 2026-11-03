import { useEffect, useId, useState } from 'react';

export function readAttachment(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.onerror = () => reject(new Error(`Could not read ${file.name}`));
    reader.onabort = () => reject(new Error(`Reading ${file.name} was cancelled`));
    reader.readAsDataURL(file);
  });
}

export default function CommentAttachments({ files, onChange, disabled, onError }) {
  const inputId = useId();
  const [dragging, setDragging] = useState(false);
  const [previews, setPreviews] = useState([]);
  useEffect(() => {
    const next = files.map((item) => ({ ...item, url: URL.createObjectURL(item.file) }));
    setPreviews(next);
    return () => next.forEach((item) => URL.revokeObjectURL(item.url));
  }, [files]);
  function select(selected) {
    if (disabled) return;
    const valid = [];
    const errors = [];
    for (const file of selected) {
      if (!/\.(png|jpe?g|webp)$/i.test(file.name)) {
        errors.push(`${file.name}: choose a PNG, JPG, or WebP image.`);
      } else if (!file.size || file.size > 8 * 1024 * 1024) {
        errors.push(`${file.name}: image must be between 1 byte and 8 MB.`);
      } else if (!files.concat(valid).some((item) => item.file.name === file.name
        && item.file.size === file.size && item.file.lastModified === file.lastModified)) {
        valid.push({ file, id: crypto.randomUUID() });
      }
    }
    onError(errors.join('\n'));
    if (valid.length) onChange([...files, ...valid]);
  }
  return (
    <div className="mt-3 space-y-3">
      <div className={`rounded-lg border-2 border-dashed p-4 ${dragging ? 'border-blue-500 bg-blue-50 dark:bg-blue-950' : 'border-neutral-300 dark:border-neutral-700'}`}
        onDragOver={(event) => { event.preventDefault(); if (!disabled) setDragging(true); }}
        onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setDragging(false); }}
        onDrop={(event) => { event.preventDefault(); setDragging(false); select([...event.dataTransfer.files]); }}>
        <label htmlFor={inputId} className="mb-2 block text-base font-semibold">Attachments</label>
        <p className="mb-3 text-sm text-black dark:text-neutral-100">Drop images here or choose files. PNG, JPG, WebP · up to 8 MB each.</p>
        <input id={inputId} type="file" accept=".png,.jpg,.jpeg,.webp" multiple disabled={disabled}
          className="block w-full text-sm file:mr-3 file:cursor-pointer file:rounded file:border file:border-neutral-300 file:px-3 file:py-2"
          onChange={(event) => { select([...event.target.files]); event.target.value = ''; }} />
      </div>
      {!!previews.length && <ul className="flex flex-wrap gap-3">
        {previews.map((item) => <li key={item.id} className="w-36 space-y-1 rounded border border-neutral-200 p-2 dark:border-neutral-700">
          <img src={item.url} alt={item.file.name} className="h-24 w-full rounded object-contain" />
          <p className="break-all text-xs">{item.file.name}</p>
          <button type="button" disabled={disabled} className="text-sm text-red-600 underline"
            aria-label={`Remove ${item.file.name}`} onClick={() => onChange(files.filter((f) => f.id !== item.id))}>Remove</button>
        </li>)}
      </ul>}
    </div>
  );
}
