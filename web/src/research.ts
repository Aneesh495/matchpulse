import type {ContextView, Deal, Estimate, History} from './types.js';
import {esc, money} from './format.js';

export function contextPanel(context: ContextView | undefined): string {
  if (!context) return '<p>No registry context loaded.</p>';
  const facts = context.facts.map(f => {
    let description = '';
    if (f.kind === 'contract') description = `Team ${esc(f.details.team_id)} · expires ${esc(f.details.expires_at?.slice(0,10))}`;
    if (f.kind === 'registration') description = `${esc(f.details.registration_kind)} · ${esc(f.details.team_id)}${f.details.parent_team_id ? ` · parent ${esc(f.details.parent_team_id)}` : ''}`;
    if (f.kind === 'availability') description = esc(f.details.status);
    if (f.kind === 'role') description = `${esc(f.details.role)} · ${esc(f.details.team_id)}`;
    return `<div class="context-fact"><strong>${esc(f.kind)}</strong><p>${description}</p><small>${esc(f.mode)} · confidence ${(100*f.confidence).toFixed(0)}% · revision ${f.revision}</small><a href="${esc(f.source_url)}" target="_blank" rel="noreferrer">Source ↗</a></div>`;
  }).join('');
  return `<p>Valid ${esc(context.valid_at.slice(0,10))}. Known by ${esc(context.known_at)}.</p>${facts || '<p>No sourced registry assertions at this cutoff.</p>'}${context.unsupported.length ? `<p>Unsupported registry fields: ${context.unsupported.map(esc).join(', ')}.</p>` : ''}${context.conflicts.length ? `<p class="negative" role="status">Conflicting sources: ${context.conflicts.map(esc).join(', ')}. Both assertions are retained.</p>` : ''}`;
}

export function feeComparison(players: History[]): string {
  if (!players.length) return '';
  return `<section class="panel compare-panel"><div class="panel-heading"><div><h2>Conditional value comparison</h2><p>Same knowledge cutoff. Observations remain a separate quantity.</p></div></div><div class="table-scroll"><table><thead><tr><th>PLAYER</th><th>CONDITIONAL MEDIAN</th><th>CURRENT INTERVAL</th><th>PRIOR INTERVAL</th><th>MOVE PROBABILITY</th><th>OBSERVED FEE</th></tr></thead><tbody>${players.map(h => {
    const e = h.estimates.at(-1);
    return `<tr><td>${esc(e?.name ?? h.person_id)}<small class="interval">${esc(e?.model_id ?? 'No estimate')}</small></td><td>${money(e?.median ?? null)}</td><td>${e?.interval?.map(v=>money(v)).join(' to ') ?? 'Unavailable'}</td><td>${e?.prior_interval?.map(v=>money(v)).join(' to ') ?? 'Unavailable'}</td><td>${e?.move_probability == null ? 'Unavailable' : (100*e.move_probability).toFixed(0)+'%'}</td><td>${h.transactions.map(d=>`${esc(d.kind)} · ${d.disclosure === 'undisclosed' ? 'Undisclosed' : money(d.guaranteed,d.currency)}<small class="interval">${esc(d.mode)} · ${esc(d.known_at.slice(0,10))}</small>`).join('') || 'No observed fee'}</td></tr>`;
  }).join('')}</tbody></table></div></section>`;
}

export function priceHistory(estimates: Estimate[], deals: Deal[]): string {
  const available = estimates.filter(e => e.median !== null);
  if (!available.length) return '<p>No available conditional estimate at this cutoff.</p>';
  const bounds = available.flatMap(e => [e.interval?.[0] ?? e.median!, e.interval?.[1] ?? e.median!]);
  const low = Math.min(...bounds), range = Math.max(1, Math.max(...bounds)-low);
  const y = (value:number) => 100-(value-low)/range*75;
  const x = (index:number) => 20+index*300/Math.max(1,estimates.length-1);
  let segment: string[] = [], lines: string[] = [], marks: string[] = [];
  estimates.forEach((e,i) => {
    if (e.median === null) {
      if (segment.length) lines.push(segment.join(' ')); segment=[];
      marks.push(`<path d="M${x(i)-3} 107l6 6m0-6-6 6" stroke="#b78b6d"><title>Estimate unavailable at v${e.version}</title></path>`);
      return;
    }
    const label = `v${e.version}, ${money(e.median)}, known ${e.known_at}`;
    segment.push(`${x(i)},${y(e.median)}`);
    if (e.interval) marks.push(`<path d="M${x(i)} ${y(e.interval[0])}V${y(e.interval[1])}" stroke="#c1d6a7" stroke-width="5"/>`);
    marks.push(`<circle cx="${x(i)}" cy="${y(e.median)}" r="3" fill="#527951" tabindex="0" role="img" aria-label="${esc(label)}"><title>${esc(label)}</title></circle>`);
  });
  if (segment.length) lines.push(segment.join(' '));
  return `<svg class="history-chart" viewBox="0 0 340 135" role="group" aria-label="Conditional estimates with support bands by saved version"><path d="M20 113h300" stroke="#d8dfd4"/>${lines.map(points=>`<polyline points="${points}" fill="none" stroke="#527951" stroke-width="2"/>`).join('')}${marks.join('')}<text x="20" y="131">Saved versions; crosses mark unavailable estimates</text></svg><p>Support bands are uncalibrated. ${deals.length} separate observed transaction(s) appear below; they do not replace the estimate series.</p>`;
}
