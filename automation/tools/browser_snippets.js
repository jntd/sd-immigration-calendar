// Browser snippets for collecting SD immigration calendar events.
//
// These are pasted into the built-in browser pane's javascript_tool, one snippet per call,
// AFTER navigating to the site named in the snippet's header (fetches must be same-origin).
// Each snippet is a complete expression. Replace the placeholders before running:
//   A = window start as YYYYMMDD (today)        e.g. 20261016
//   B = window end   as YYYYMMDD (today + 31)   e.g. 20261116
//   AISO / BISO = the same dates as YYYY-MM-DD (County Library RSS only)
//   PAGES = list of month-page paths (Granicus)  ['/path', '/path/-curm-11/-cury-2026']
//   FEED  = feed path with the filters          '/events/feed/ical?age_groups%5B30%5D=30'
//
// Output is text the session copies into a raw/ file:
//   *.tsv  one line per event, 10 tab-separated columns, each cell holds the iCal property's
//          parameters + value exactly as published (e.g. ";TZID=America/Los_Angeles:20261014T100000")
//          UID DTSTART DTEND SUMMARY LOCATION ROOM URL CATEGORIES STATUS DESCRIPTION
//          DESCRIPTION is plain text, HTML removed, cut to about 300 characters.
//   sdcl_rss_extract.txt  one line per event, 11 fields separated by " || "
//
// Tested 2026-10-16: FEED_TSV (Legal Aid), GRANICUS_TSV (Chula Vista), SDCL_RSS, Eventbrite description.
// IG_CAPTIONS and IG_POST were used 2026-10-13/15.


// ---------------------------------------------------------------------------------------------
// FEED_TSV  -  any site with a whole-calendar iCal feed.
// LibraryCalendar (Oceanside, Escondido, Coronado):  FEED = '/events/feed/ical?<same filters as the page>'
// The Events Calendar / WordPress (Legal Aid, SDVLP, MAAC, Casa Familiar): FEED = '/events/list/?ical=1'
// Navigate to any page on that site first.
// ---------------------------------------------------------------------------------------------
(async (FEED, A, B) => {
  const D = v => { if (!v) return ''; let x = v.slice(v.indexOf(':') + 1).replace(/<[^>]+>/g, ' ').replace(/&nbsp;|&amp;nbsp;/g, ' ').replace(/(\\n)+/g, ' ').replace(/\s+/g, ' ').trim(); if (x.length > 300) x = x.slice(0, 300).replace(/\\+$/, '').replace(/\s\S*$/, '') + ' …'; return x ? ':' + x : ''; };
  let t = await Promise.race([fetch(FEED).then(r => r.text()), new Promise(r => setTimeout(() => r(''), 30000))]);
  t = t.replace(/\r?\n[ \t]/g, '');
  const ev = t.match(/BEGIN:VEVENT[\s\S]*?END:VEVENT/g) || [];
  const g = (e, k) => { const m = e.match(new RegExp('^' + k + '([;:][^\\r\\n]*)$', 'm')); return m ? m[1].replace(/\t/g, ' ') : ''; };
  const out = ev.filter(e => { const d = (e.match(/DTSTART[^:\n]*:(\d{8})/) || [])[1]; return d >= A && d <= B; })
    .map(e => [g(e, 'UID'), g(e, 'DTSTART'), g(e, 'DTEND'), g(e, 'SUMMARY'), g(e, 'LOCATION'), g(e, 'ROOM'), g(e, 'URL'), g(e, 'CATEGORIES'), g(e, 'STATUS'), D(g(e, 'DESCRIPTION'))].join('\t'));
  return (t ? 'TOTAL ' + ev.length : 'NO FEED (timeout or empty)') + ' KEPT ' + out.length + '\n' + out.join('\n');
})(FEED, 'A', 'B')


// ---------------------------------------------------------------------------------------------
// GRANICUS_TSV  -  Chula Vista, Carlsbad, National City (Granicus calendars, per-event .ics).
// Reads the event IDs from each month page, then downloads each event's .ics.
// The .ics has no UID and no time zone; build_batch.py adds both.
// If it runs past the 50-second limit, call it once per month page.
// ---------------------------------------------------------------------------------------------
(async (PAGES, A, B) => {
  const D = v => { if (!v) return ''; let x = v.slice(v.indexOf(':') + 1).replace(/<[^>]+>/g, ' ').replace(/&nbsp;|&amp;nbsp;/g, ' ').replace(/(\\n)+/g, ' ').replace(/\s+/g, ' ').trim(); if (x.length > 300) x = x.slice(0, 300).replace(/\\+$/, '').replace(/\s\S*$/, '') + ' …'; return x ? ':' + x : ''; };
  const ids = new Set();
  for (const p of PAGES) { const h = await (await fetch(p)).text(); (h.match(/Calendar\/Event\/(\d+)\//g) || []).forEach(m => ids.add(m.match(/\d+/)[0])); }
  const out = [];
  for (const id of ids) {
    let t = await (await fetch('/Home/Components/Calendar/Event/ICalendar?ID=' + id + '&IsPublished=True')).text();
    t = t.replace(/\r?\n[ \t]/g, '');
    const g = k => { const m = t.match(new RegExp('^' + k + '([;:][^\\r\\n]*)$', 'm')); return m ? m[1].replace(/\t/g, ' ') : ''; };
    const d = (g('DTSTART').match(/(\d{8})/) || [])[1];
    if (!(d >= A && d <= B)) continue;
    out.push(['', g('DTSTART'), g('DTEND'), g('SUMMARY'), g('LOCATION'), '', ':' + location.origin + '/Home/Components/Calendar/Event/' + id, '', '', D(g('DESCRIPTION'))].join('\t'));
  }
  out.sort((x, y) => x.split('\t')[1] < y.split('\t')[1] ? -1 : 1);
  return 'IDS ' + ids.size + ' KEPT ' + out.length + '\n' + out.join('\n');
})(PAGES, 'A', 'B')


// ---------------------------------------------------------------------------------------------
// SDCL_RSS  -  San Diego County Library (BiblioCommons RSS; no iCal).
// Navigate to https://sdcl.bibliocommons.com/events first (the gateway allows that origin).
// Fields: guid || title || start || end || branch || street, city, zip || link || cancelled || virtual || categories || description
// ---------------------------------------------------------------------------------------------
(async (AISO, BISO) => {
  const base = 'https://gateway.bibliocommons.com/v2/libraries/sdcl/rss/events?types=60d3d4f817df9637003ba141%2C60d3d686618cfb3000ddb6c4%2C60d3d5c99880a342007cde20&page=';
  const all = [], seen = new Set(), info = []; let last = '';
  for (let p = 1; p <= 12; p++) {
    let r; try { r = await fetch(base + p); } catch (e) { info.push('p' + p + ' fetch err'); break; }
    const x = new DOMParser().parseFromString(await r.text(), 'text/xml');
    const its = [...x.querySelectorAll('item')];
    if (!its.length) { info.push('p' + p + ' empty'); break; }
    const g = (i, t) => { const e = i.getElementsByTagName(t)[0]; return e ? e.textContent.trim() : ''; };
    its.forEach(i => {
      const id = g(i, 'guid').split('/').pop(); if (seen.has(id)) return; seen.add(id);
      const loc = i.getElementsByTagName('bc:location')[0];
      const lg = t => { if (!loc) return ''; const e = loc.getElementsByTagName(t)[0]; return e ? e.textContent.trim() : ''; };
      const cats = [...i.getElementsByTagName('category')].map(c => c.textContent.trim()).join(';');
      let desc = new DOMParser().parseFromString(g(i, 'description'), 'text/html').body.textContent.replace(/\s+/g, ' ').replace(/\|/g, '/').trim();
      if (desc.length > 300) desc = desc.slice(0, 300).replace(/\s\S*$/, '') + ' …';
      const s = g(i, 'bc:start_date_local'); last = s;
      all.push([id, g(i, 'title'), s, g(i, 'bc:end_date_local'), lg('bc:name'), [(lg('bc:number') + ' ' + lg('bc:street')).trim(), lg('bc:city'), lg('bc:zip')].filter(Boolean).join(', '), g(i, 'link'), g(i, 'bc:is_cancelled'), g(i, 'bc:is_virtual'), cats, desc].join(' || '));
    });
    info.push('p' + p + ' ' + its.length + ' last ' + last);
    if (last.slice(0, 10) > BISO) break;
  }
  const keep = all.filter(l => { const f = l.split(' || '); return f[2].slice(0, 10) <= BISO && (f[3] || f[2]).slice(0, 10) >= AISO; });
  return info.join(' | ') + '\nKEPT ' + keep.length + '\n' + keep.join('\n');
})('AISO', 'BISO')


// ---------------------------------------------------------------------------------------------
// EVENTBRITE_IDS  -  run once on each search page, after navigating to
// https://www.eventbrite.com/d/ca--san-diego/{term}/   Collects event IDs across searches.
// ---------------------------------------------------------------------------------------------
(async () => {
  await new Promise(r => setTimeout(r, 5000));
  const s = new Set(JSON.parse(sessionStorage.getItem('ebids') || '[]'));
  [...document.querySelectorAll('a[href*="/e/"]')].forEach(a => { const m = a.href.match(/-(\d{9,})(\?|$)/); if (m) s.add(m[1]); });
  sessionStorage.setItem('ebids', JSON.stringify([...s]));
  return s.size;
})()


// ---------------------------------------------------------------------------------------------
// EVENTBRITE_TSV  -  after the searches, on any eventbrite.com page: downloads each event's .ics,
// keeps those in the window, and takes the description from the event page (the .ics description
// only says "For details, go here"). If it runs past 50 seconds, pass SLICE = [0, 30] then [30, 60].
// ---------------------------------------------------------------------------------------------
(async (A, B, SLICE) => {
  const ids = JSON.parse(sessionStorage.getItem('ebids') || '[]').slice(SLICE[0], SLICE[1]);
  const out = []; let skip = 0;
  for (const id of ids) {
    try {
      let t = await Promise.race([fetch('/calendar.ics?eid=' + id + '&calendar=ical').then(r => r.text()), new Promise(r => setTimeout(() => r(''), 8000))]);
      t = t.replace(/\r?\n[ \t]/g, '');
      const g = k => { const m = t.match(new RegExp('^' + k + '([;:][^\\r\\n]*)$', 'm')); return m ? m[1].replace(/\t/g, ' ') : ''; };
      const d = (g('DTSTART').match(/(\d{8})/) || [])[1];
      if (!d || d < A || d > B) { skip++; continue; }
      let desc = '';
      try {
        const h = await Promise.race([fetch('/e/' + id).then(r => r.text()), new Promise(r => setTimeout(() => r(''), 8000))]);
        const doc = new DOMParser().parseFromString(h, 'text/html');
        const ld = [...doc.querySelectorAll('script[type="application/ld+json"]')].map(s => { try { return JSON.parse(s.textContent); } catch (e) { return null; } }).flat().filter(Boolean);
        desc = ((ld.find(o => /Event/.test(o['@type'] || '')) || {}).description || '').replace(/\s+/g, ' ').trim();
        if (desc.length > 300) desc = desc.slice(0, 300).replace(/\s\S*$/, '') + ' …';
        desc = desc.replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,');
      } catch (e) {}
      out.push([':' + id + '@eventbrite.com', g('DTSTART'), g('DTEND'), g('SUMMARY'), g('LOCATION'), '', ':https://www.eventbrite.com/e/' + id, '', '', desc ? ':' + desc : ''].join('\t'));
    } catch (e) { skip++; }
  }
  return 'IDS ' + ids.length + ' IN-WINDOW ' + out.length + ' SKIPPED ' + skip + '\n' + out.join('\n');
})('A', 'B', [0, 60])


// ---------------------------------------------------------------------------------------------
// PAGE_TEXT  -  agency event pages without iCal: the visible text of the main content.
// ---------------------------------------------------------------------------------------------
(async () => {
  await new Promise(r => setTimeout(r, 3500));
  return (document.querySelector('main') || document.body).innerText.replace(/\s+/g, ' ').slice(0, 3500);
})()


// ---------------------------------------------------------------------------------------------
// IG_CAPTIONS  -  an Instagram profile, logged in. The grid image's alt text is the caption.
// Keeps only posts whose caption looks like an event. Read-only: never like, follow or comment.
// ---------------------------------------------------------------------------------------------
(async () => {
  await new Promise(r => setTimeout(r, 9000));
  const l = [...document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]')].slice(0, 12)
    .map(x => [x.getAttribute('href'), ((x.querySelector('img') || {}).alt || '').replace(/\s+/g, ' ')]);
  const re = /join us|register|rsvp|workshop|clinic|class|taller|evento|event|webinar|training|fair|feria|session|town hall|festival|save the date|\d ?(am|pm)\b|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? \d|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|this (mon|tue|wed|thu|fri|sat|sun)|tomorrow|tonight/i;
  return location.pathname + ' n=' + l.length + '\n' + l.filter(x => re.test(x[1])).map(x => x[0] + ' :: ' + x[1].slice(0, 450)).join('\n');
})()


// ---------------------------------------------------------------------------------------------
// IG_POST  -  one Instagram post, when the grid caption was cut off before the date or time.
// ---------------------------------------------------------------------------------------------
(async () => {
  await new Promise(r => setTimeout(r, 7000));
  const b = [...document.querySelectorAll('span,div[role=button],button')].find(e => e.innerText && e.innerText.trim() === 'more');
  if (b) b.click();
  await new Promise(r => setTimeout(r, 1500));
  const cap = [...document.querySelectorAll('h1, span')].map(s => s.innerText).sort((a, b) => b.length - a.length)[0] || '';
  return cap.slice(0, 2000) + ' ## POSTED ' + ((document.querySelector('time') || {}).dateTime || '');
})()
