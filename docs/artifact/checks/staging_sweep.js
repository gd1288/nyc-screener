// Regression sweep for docs/artifact/staging.html. Paste into the browser tool's JavaScript console with the
// page open (navigate to file:///Users/bobjoe/Desktop/nyc-screener/docs/artifact/staging.html first).
// Loads every embedded screener listing, visits all four tabs, and reports anything broken. A healthy run:
// exc 0, nanCases 0, orderViolations 0, badLinks 0. Read the console for errors separately.
(() => {
  const tabs = ['ov', 'cf', 'st', 'as'], click = t => document.querySelector('.tabs button[data-t="' + t + '"]').click();
  const visible = () => /NaN|Infinity|undefined/.test(document.body.innerText);
  const svgBad = () => [...document.querySelectorAll('svg *')].some(e => /NaN|Infinity/.test(['d', 'cx', 'cy', 'x', 'y', 'width', 'height'].map(k => e.getAttribute(k) || '').join(' ')));
  const r = { listings: LISTINGS.rows.length, exc: 0, nanCases: 0, svgCases: 0, orderViolations: 0, withBaseIrr: 0, badLinks: 0, rateChips: {} };
  for (const row of LISTINGS.rows) {
    try {
      loadListing(row);
      if (B.irr != null) {  // downside worlds must never beat base, upside never fall below it
        r.withBaseIrr++;
        SCS.forEach(x => { const g = x.n.g, ir = x.m.irr; if (g === 'down' && ir != null && ir > B.irr + 1e-9) r.orderViolations++; if (g === 'up' && (ir == null || ir < B.irr - 1e-9)) r.orderViolations++; });
      }
      tabs.forEach(t => { click(t); if (visible()) r.nanCases++; if (svgBad()) r.svgCases++; });
      const d = document.querySelector('#terms .term:nth-child(3) .dot').className; r.rateChips[d] = (r.rateChips[d] || 0) + 1;
      const L = linkSets(row); [...L.off, ...L.map, ...L.find].forEach(([, u]) => { if (!/^https:\/\//.test(u)) r.badLinks++; });
    } catch (e) { r.exc++; r.firstError = r.firstError || (row.a + ': ' + e.message); }
  }
  loadSample(); click('ov');
  r.sampleRestored = { irr: pc(B.irr), rate: S.rate };  // expect 13.0% and 0.045 (the 421 Harris fixture)
  return r;
})();
