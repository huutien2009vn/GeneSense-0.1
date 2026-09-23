const paths = {
  heart: '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/><path d="M3 12h5l2-4 3 8 2-4h6"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
  family: '<circle cx="9" cy="7" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 4a3 3 0 0 1 0 6M18 13a5 5 0 0 1 3 5v3"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
  history: '<path d="M3 11a9 9 0 1 1 2 7M3 4v7h7M12 7v5l3 2"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.4 1.4M17.6 17.6 19 19M5 19l1.4-1.4M17.6 6.4 19 5"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  edit: '<path d="m16 3 5 5-12 12-6 1 1-6L16 3ZM13 6l5 5"/>',
  leaf: '<path d="M20 3C9 1 2 6 4 14c2 8 17 6 16-11ZM4 21 15 10"/>',
  logout: '<path d="M9 4H4v16h5M10 12h11m-4-4 4 4-4 4"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v.1"/>',
  sparkles: '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3ZM20 2v4M18 4h4"/>',
  bluetooth: '<path d="m7 7 12 10-7 5V2l7 5L7 17"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14-5L3 9m0-6v6h6M4 13a8 8 0 0 0 14 5l3-3m0 6v-6h-6"/>',
  chart: '<path d="M4 3v17h17M7 14l4-5 4 3 5-7"/>',
  message: '<path d="M21 11a8 8 0 0 1-8 8H6l-4 3V5a3 3 0 0 1 3-3h8a8 8 0 0 1 8 9Z"/><path d="M7 8h9M7 12h6"/>',
  pressure: '<path d="M2 12h4l3-8 6 16 3-8h4"/>',
  drop: '<path d="M12 2C9 7 4 11 4 15a8 8 0 0 0 16 0c0-4-5-8-8-13Z"/><path d="M8 15a4 4 0 0 0 4 4"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  document: '<path d="M6 2h8l4 4v16H6z"/><path d="M14 2v5h5M9 12h6M9 16h6"/>',
  scan: '<path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3M8 12h8M10 9h4M10 15h4"/>',
  trash: '<path d="M4 7h16M9 3h6l1 4H8l1-4ZM7 7l1 14h8l1-14M10 11v6M14 11v6"/>',
};
export function icon(name) {
  return '<svg class="icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (paths[name] || paths.heart) + '</svg>';
}
export function hydrateIcons(root = document) {
  root.querySelectorAll("[data-icon]").forEach(el => { el.innerHTML = icon(el.dataset.icon); });
}
