import { useEffect, useState } from "react";

type OllamaModel = { name: string; size?: number; modified_at?: string };

type Props = {
  value: string;
  onChange: (model: string) => void;
  /** Disable interactions while a stream is in flight. */
  disabled?: boolean;
};

/**
 * Dropdown listing every model installed in the local Ollama instance.
 *
 * The list is fetched once on mount from the backend's `/api/models` proxy.
 * The user picks any model — no capability filtering (per design); if the
 * pick can't tool-call or can't see images, the agent will surface that
 * error naturally.
 */
export function ModelSelector({ value, onChange, disabled }: Props) {
  const [models, setModels] = useState<OllamaModel[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch("/api/models");
        const data = await r.json();
        if (cancelled) return;
        if (!r.ok || data.error) {
          setError(data.error ?? `HTTP ${r.status}`);
          setModels([]);
        } else {
          setModels(data.models ?? []);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // If the persisted choice isn't in the fetched list, still show it as
  // the selected option so the dropdown doesn't lie about what's active.
  const hasCurrent = models.some((m) => m.name === value);
  const options = hasCurrent || !value ? models : [{ name: value }, ...models];

  if (loading) {
    return <span className="model-selector model-selector--muted">loading models…</span>;
  }
  if (error) {
    return (
      <span className="model-selector model-selector--error" title={error}>
        ⚠ ollama unreachable
      </span>
    );
  }

  return (
    <select
      className="model-selector"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      title="Model used by both the planner and the vision pass"
    >
      {options.length === 0 && <option value="">(no models installed)</option>}
      {options.map((m) => (
        <option key={m.name} value={m.name}>
          {m.name}
        </option>
      ))}
    </select>
  );
}
