import { useEffect, useMemo, useRef } from "react";
import { Paperclip, X } from "lucide-react";
import { Button } from "./button";

export function SupportImages({ files, onChange, onError, label, disabled = false }: {
  files: File[]; onChange: (files: File[]) => void; onError: (error: string) => void;
  label: string; disabled?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const urls = useMemo(() => files.map(f => URL.createObjectURL(f)), [files]);
  useEffect(() => () => urls.forEach(URL.revokeObjectURL), [urls]);
  return <div className="flex flex-wrap items-center gap-2">
    {files.map((f, i) => <div key={i} className="relative">
      <img src={urls[i]} alt={f.name} className="h-14 w-14 rounded-md object-cover" />
      <button type="button" disabled={disabled} aria-label={`× ${f.name}`} className="absolute -right-1 -top-1 rounded-full bg-destructive p-1 text-white" onClick={() => onChange(files.filter((_, j) => i !== j))}><X size={12} /></button>
    </div>)}
    <input ref={input} type="file" accept="image/jpeg,image/png,image/webp,image/gif" multiple hidden onChange={e => {
      const incoming = Array.from(e.target.files || []); e.target.value = "";
      if (files.length + incoming.length > 3 || incoming.some(f => f.size > 5 * 1024 * 1024 || !/^image\/(jpeg|png|webp|gif)$/.test(f.type))) { onError(label + ": JPEG, PNG, WebP, GIF · ≤ 3 × 5 MB"); return; }
      onChange([...files, ...incoming]);
    }} />
    <Button type="button" variant="outline" size="sm" disabled={disabled || files.length >= 3} onClick={() => input.current?.click()}><Paperclip size={16} />{label}</Button>
    <span className="text-xs text-muted-foreground">{files.length}/3 · ≤ 5 MB</span>
  </div>;
}
