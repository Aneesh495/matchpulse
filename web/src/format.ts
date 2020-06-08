export const esc = (value: unknown): string => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
export const money = (value: number | null, currency = 'EUR'): string => value === null ? 'Unavailable' : new Intl.NumberFormat('en-GB', {style:'currency',currency,notation:'compact',maximumFractionDigits:2}).format(value);
