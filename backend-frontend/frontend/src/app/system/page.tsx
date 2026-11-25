'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { fetchModelManifest, fetchReadiness, fetchTelemetry } from '@/lib/api';
import type { ModelManifest, ReadyResponse, TelemetrySnapshot } from '@/types';
import { ErrorState, Loading } from '@/components/States';
import { MODEL_LABELS } from '@/lib/format';

const card = 'rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900';

function Checksums({ title, values }: { title: string; values?: Record<string, string> }) {
  if (!values) return null;
  return (
    <details className="rounded-lg bg-slate-50 p-3 text-xs dark:bg-slate-800/60">
      <summary className="cursor-pointer font-semibold">
        {title} ({Object.keys(values).length} files)
      </summary>
      <table className="mt-2 w-full font-mono text-[11px]">
        <tbody>
          {Object.entries(values).map(([name, hash]) => (
            <tr key={name}>
              <th scope="row" className="pr-3 text-left font-normal">
                {name}
              </th>
              <td className="break-all">{hash}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

export default function SystemPage() {
  const [manifest, setManifest] = useState<ModelManifest | null>(null);
  const [ready, setReady] = useState<ReadyResponse | null>(null);
  const [readyError, setReadyError] = useState<unknown>(null);
  const [telemetry, setTelemetry] = useState<TelemetrySnapshot | null>(null);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(() => {
    setError(null);
    fetchModelManifest().then(setManifest).catch(setError);
    fetchReadiness()
      .then((r) => {
        setReady(r);
        setReadyError(null);
      })
      .catch(setReadyError);
    fetchTelemetry()
      .then(setTelemetry)
      .catch(() => setTelemetry(null));
  }, []);
  useEffect(load, [load]);

  if (error) return <ErrorState error={error} onRetry={load} />;
  if (!manifest) return <Loading label="Loading model manifest…" />;
  const release = manifest.dataset_release;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3 border-b border-slate-200 pb-4 dark:border-slate-800">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight">System, manifest and reproducibility</h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">Everything on this page is read live from the Go API.</p>
        </div>
        <button
          type="button"
          onClick={load}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
        >
          Refresh
        </button>
      </header>

      <section aria-labelledby="status-heading" className={card}>
        <h2 id="status-heading" className="text-base font-bold">
          API status
        </h2>
        {readyError ? (
          <div className="mt-3">
            <ErrorState error={readyError} />
          </div>
        ) : !ready ? (
          <Loading label="Checking readiness…" />
        ) : (
          <dl className="mt-3 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
            <div>
              <dt className="text-xs text-slate-500">Readiness</dt>
              <dd className={`font-bold ${ready.status === 'ready' ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-700'}`}>
                {ready.status}
              </dd>
            </div>
            {Object.entries(ready.checks).map(([name, value]) => (
              <div key={name}>
                <dt className="text-xs text-slate-500">{name}</dt>
                <dd className="font-mono">{value}</dd>
              </div>
            ))}
            <div>
              <dt className="text-xs text-slate-500">Database</dt>
              <dd className="font-mono">{ready.database_kind}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Catalog / known users</dt>
              <dd className="font-mono">
                {ready.catalog_items.toLocaleString('en-US')} / {ready.known_users.toLocaleString('en-US')}
              </dd>
            </div>
          </dl>
        )}
        <h3 className="mt-5 text-sm font-bold">Process telemetry (since start)</h3>
        {telemetry ? (
          <dl className="mt-2 grid grid-cols-2 gap-3 font-mono text-sm md:grid-cols-4">
            {[
              ['Requests', telemetry.total_requests],
              ['2xx / 4xx / 5xx', `${telemetry.responses_2xx} / ${telemetry.responses_4xx} / ${telemetry.responses_5xx}`],
              ['Rate limited', telemetry.rate_limited],
              ['Recommendations served', telemetry.recommendations_served],
              ['Fallback responses', telemetry.fallback_responses],
              ['Feedback (persisted)', Object.values(telemetry.feedback_by_action).reduce((a, b) => a + b, 0)],
              ['Mean latency', telemetry.total_requests ? `${telemetry.average_latency_ms.toFixed(2)} ms` : 'no requests yet'],
              ['Uptime', `${telemetry.uptime_seconds} s`],
            ].map(([label, value]) => (
              <div key={String(label)}>
                <dt className="font-sans text-xs text-slate-500">{label}</dt>
                <dd>{String(value)}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="mt-2 text-xs text-slate-600">Telemetry unavailable.</p>
        )}
      </section>

      <section aria-labelledby="dataset-heading" className={card}>
        <h2 id="dataset-heading" className="text-base font-bold">
          Dataset release
        </h2>
        <dl className="mt-3 grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
          <div>
            <dt className="text-xs text-slate-500">Release</dt>
            <dd>{String(release.name)}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Official record</dt>
            <dd>
              <a
                className="text-indigo-700 underline dark:text-indigo-300"
                href={String(release.official_url)}
                target="_blank"
                rel="noreferrer"
              >
                {String(release.official_url)}
              </a>
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Protocol</dt>
            <dd>{String(release.protocol)}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Target</dt>
            <dd>{String(release.target_definition)}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Eligible users / items</dt>
            <dd>
              {Number(release.eligible_users).toLocaleString('en-US')} / {Number(release.eligible_items).toLocaleString('en-US')}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Paper</dt>
            <dd>{String(release.paper)}</dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="manifest-heading" className={card}>
        <h2 id="manifest-heading" className="text-base font-bold">
          Current model manifest
        </h2>
        <p className="mt-1 font-mono text-xs text-slate-600 dark:text-slate-400">
          manifest v{manifest.manifest_version} · bundle generated {manifest.generated_at} · offline models{' '}
          {manifest.source_model_manifest_generated_at} · checksums verified at load: {manifest.bundle_verified_at_load ? 'yes' : 'no'}
        </p>
        <p className="mt-2 text-sm">
          Selected: <strong>{MODEL_LABELS[manifest.current_model] ?? manifest.current_model}</strong> · fallback:{' '}
          <strong>{MODEL_LABELS[manifest.fallback_model] ?? manifest.fallback_model}</strong> · server default:{' '}
          <code className="font-mono">{manifest.active_default_model}</code>
        </p>
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          {manifest.models.map((m) => (
            <div key={m.id} className="rounded-lg border border-slate-200 p-4 dark:border-slate-700">
              <p className="font-mono text-xs">{m.id}</p>
              <p className="mt-1 font-bold">
                {m.name} <span className="ml-1 rounded bg-slate-200 px-1 text-[10px] uppercase dark:bg-slate-700">{m.status}</span>
              </p>
              <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">{m.description}</p>
              {m.weights && (
                <p className="mt-2 font-mono text-xs">
                  α (Item-CF) {m.weights.alpha_cf} · β (LightGCN) {m.weights.beta_extension} · γ (popularity) {m.weights.gamma_popularity}
                </p>
              )}
            </div>
          ))}
        </div>
        <h3 className="mt-5 text-sm font-bold">Serving artifacts</h3>
        <ul className="mt-2 list-disc pl-5 text-xs">
          {Object.entries(manifest.serving).map(([name, info]) => (
            <li key={name}>
              <strong>{name}</strong>:{' '}
              {Object.entries(info)
                .map(([k, v]) => `${k}: ${v}`)
                .join(' · ')}
            </li>
          ))}
        </ul>
        <h3 className="mt-5 text-sm font-bold">Reason-code rules</h3>
        <ul className="mt-2 space-y-2 text-xs">
          {manifest.reason_code_rules.map((rule) => (
            <li key={rule.code} className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800/60">
              <code className="font-bold">{rule.code}</code> — {rule.enabled ? 'enabled' : 'disabled'}: {rule.description}
              <br />
              <span className="font-mono text-[11px] text-slate-600 dark:text-slate-400">
                required evidence: {rule.required_evidence.join(', ')}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="repro-heading" className={card}>
        <h2 id="repro-heading" className="text-base font-bold">
          Reproducibility
        </h2>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">
          <li>
            Rebuild the serving bundle from the frozen offline artifacts:{' '}
            <code className="font-mono text-xs">python backend-frontend/scripts/export_item_similarity.py</code> then{' '}
            <code className="font-mono text-xs">python backend-frontend/scripts/generate_serving_bundle.py</code>.
          </li>
          <li>
            The API refuses to start if any bundle file differs from the checksums below or if any served reason lacks required evidence.
          </li>
          <li>
            Start everything with <code className="font-mono text-xs">docker compose up --build</code> from{' '}
            <code className="font-mono text-xs">backend-frontend/</code>.
          </li>
        </ol>
        <div className="mt-3 space-y-2">
          <Checksums title="Serving bundle SHA-256" values={manifest.bundle_sha256} />
          <Checksums title="Frozen offline artifacts SHA-256" values={manifest.source_artifacts_sha256} />
        </div>
      </section>

      <section aria-labelledby="arch-heading" className={card}>
        <h2 id="arch-heading" className="text-base font-bold">
          Architecture
        </h2>
        <pre className="mt-3 overflow-x-auto rounded-lg bg-slate-900 p-4 font-mono text-xs leading-relaxed text-slate-100">
          {`Browser ── Next.js 14 (port 3000, rewrites /api → API)
              │
              ▼
Go API (chi, port 8080) ── loads frozen serving bundle at start (checksums + evidence verified)
  ├─ recommender   filter/truncate frozen lists, cold-start fallback, per-request model
  ├─ explanation   approved reason codes, evidence validation
  ├─ httpapi       validation, CORS, rate limiting, request IDs
  ├─ telemetry     latency header, counters (/metrics)
  └─ database ──── PostgreSQL 16: feedback, recommendation logs, API request logs
              ▲
Offline Python pipeline (model/) ── trains/evaluates; never called at request time`}
        </pre>
      </section>
    </div>
  );
}
