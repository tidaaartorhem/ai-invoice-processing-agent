import { useEffect, useState } from 'react';
import { gbp } from './format';
import type {
  AnalyticsBundle, DuplicatesBundle, MetaBundle, PasteSample, QueueBundle,
} from './types';
import type { Registers } from './client-match';
import { Queue } from './components/Queue';
import { Duplicates } from './components/Duplicates';
import { Discounts } from './components/Discounts';
import { Analytics } from './components/Analytics';
import { PasteInvoice } from './components/PasteInvoice';
import './styles.css';

type Tab = 'queue' | 'duplicates' | 'discounts' | 'paste' | 'analytics';

async function load<T>(name: string): Promise<T> {
  const res = await fetch(`./${name}`);
  if (!res.ok) throw new Error(`failed to load ${name}`);
  return res.json() as Promise<T>;
}

export function App() {
  const [tab, setTab] = useState<Tab>('queue');
  const [queue, setQueue] = useState<QueueBundle | null>(null);
  const [dups, setDups] = useState<DuplicatesBundle | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsBundle | null>(null);
  const [meta, setMeta] = useState<MetaBundle | null>(null);
  const [registers, setRegisters] = useState<Registers | null>(null);
  const [samples, setSamples] = useState<PasteSample[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      load<QueueBundle>('queue.json').then(setQueue),
      load<DuplicatesBundle>('duplicates.json').then(setDups),
      load<AnalyticsBundle>('analytics.json').then(setAnalytics),
      load<MetaBundle>('meta.json').then(setMeta),
      load<Registers>('registers.json').then(setRegisters),
      load<PasteSample[]>('paste_samples.json').then(setSamples),
    ]).catch((e) => setError(String(e)));
  }, []);

  const tabs: [Tab, string][] = [
    ['queue', 'Review queue'],
    ['duplicates', 'Duplicates'],
    ['discounts', 'Discounts'],
    ['paste', 'Paste an invoice'],
    ['analytics', 'Analytics'],
  ];

  return (
    <>
      <header className="top">
        <div className="container">
          <h1>Matchboard <span className="accent">— invoice matching for small-business AP</span></h1>
          <p className="sub">
            {queue ? (
              <>Monday {queue.review_date} replay · {queue.queue_size} invoices · {gbp(analytics?.window_spend ?? null)} under review · nothing here pays anything without a human</>
            ) : 'Loading the Monday-morning replay…'}
          </p>
          <nav className="tabs">
            {tabs.map(([t, label]) => (
              <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>{label}</button>
            ))}
          </nav>
        </div>
      </header>
      <main>
        <div className="container">
          {error && <div className="card"><p className="missing">Could not load data: {error}</p></div>}
          {!error && !queue && <div className="card"><p className="hint">Loading…</p></div>}
          {queue && tab === 'queue' && <Queue bundle={queue} />}
          {dups && tab === 'duplicates' && <Duplicates bundle={dups} />}
          {queue && tab === 'discounts' && <Discounts bundle={queue} />}
          {registers && queue && tab === 'paste' && (
            <PasteInvoice registers={registers} samples={samples} reviewDate={queue.review_date} />
          )}
          {analytics && meta && tab === 'analytics' && <Analytics bundle={analytics} meta={meta} />}
        </div>
      </main>
      <footer className="foot">
        <div className="container">
          Invoices: real line-item records from the UCI Online Retail dataset (UK retailer, Dec 2010 – Dec 2011).
          PO/GRN registers and payment terms are the walkthrough's seeded company records — see <span className="mono">services/seed.py</span>.
          Deterministic pipeline: no models, no external calls. <a href="https://github.com/tidaaartorhem/ai-invoice-processing-agent">GitHub</a>
        </div>
      </footer>
    </>
  );
}
