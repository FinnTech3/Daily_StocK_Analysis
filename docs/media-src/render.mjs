// render.mjs: turn the pages written by make_charts.py (and a Markdown answer) into PNG images.
//
//   node render.mjs html page.html out.png [scale]        screenshot the #frame element of a page
//   node render.mjs md answer.md out.png "title bar text"  a Markdown answer shown as a card (screenshot-1)
//
// Playwright must be installed (set PW_ROOT to a folder that has it in node_modules if it is not next to this file).
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const { chromium } = createRequire(process.env.PW_ROOT ? `${process.env.PW_ROOT}/` : import.meta.url)('playwright');
const [, , mode, input, out, third] = process.argv;
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function markdownToHtml(md) {
  const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`(.+?)`/g, '<code>$1</code>').replace(/\*(.+?)\*/g, '<i>$1</i>');
  const lines = md.split('\n');
  const html = [];
  let i = 0;
  while (i < lines.length) {
    const ln = lines[i];
    if (/^\|/.test(ln) && /^\|[-: |]+\|$/.test(lines[i + 1] || '')) {
      const cells = (r) => r.replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
      const align = cells(lines[i + 1]).map((c) => (c.endsWith(':') ? 'right' : 'left'));
      const cls = (c) => (/^Bullish$|^Lean bullish$/.test(c) ? 'up' : /bearish$/i.test(c) ? 'down' : '');
      let h = '<table><tr>' + cells(ln).map((c, k) => `<th style="text-align:${align[k]}">${inline(c)}</th>`).join('') + '</tr>';
      i += 2;
      while (i < lines.length && /^\|/.test(lines[i])) {
        h += '<tr>' + cells(lines[i]).map((c, k) => `<td class="${cls(c)}" style="text-align:${align[k]}">${inline(c)}</td>`).join('') + '</tr>';
        i++;
      }
      html.push(h + '</table>');
      continue;
    }
    if (/^- /.test(ln)) {
      let h = '<ul>';
      while (i < lines.length && /^- /.test(lines[i])) { h += `<li>${inline(lines[i].slice(2))}</li>`; i++; }
      html.push(h + '</ul>');
      continue;
    }
    if (ln.trim()) html.push(`<p>${inline(ln)}</p>`);
    i++;
  }
  return html.join('');
}

const browser = await chromium.launch();
if (mode === 'html') {
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 }, deviceScaleFactor: Number(third || 2) });
  await page.goto(pathToFileURL(path.resolve(input)).href);
  await page.locator('#frame').screenshot({ path: out });
} else if (mode === 'md') {
  const body = markdownToHtml(fs.readFileSync(input, 'utf8'));
  const page = await browser.newPage({ viewport: { width: 1200, height: 800 }, deviceScaleFactor: 2 });
  await page.setContent(`<style>
  body{margin:0;background:linear-gradient(135deg,#0f766e,#064e3b);padding:40px;font-family:Inter,system-ui,sans-serif;color:#1f2937}
  .card{width:1040px;margin:auto;background:#fff;border-radius:18px;padding:26px 40px 22px;box-shadow:0 24px 60px rgba(0,0,0,.35)}
  .bar{font-size:15px;color:#64748b;margin-bottom:12px}p,li{font-size:17px;line-height:1.5;margin:5px 0}ul{margin:4px 0 10px;padding-left:26px}
  table{border-collapse:collapse;margin:10px 0;font-size:17px}th,td{border:1px solid #e5e7eb;padding:7px 16px}th{background:#f1f5f9}
  td.up{color:#047857;font-weight:700}td.down{color:#b91c1c;font-weight:700}code{background:#f1f5f9;border-radius:4px;padding:1px 5px}
  </style><div class="card"><div class="bar">${esc(third || '')}</div>${body}</div>`);
  await page.locator('.card').screenshot({ path: out });
} else {
  console.error('usage: node render.mjs html|md input output [scale|title]');
  process.exit(2);
}
await browser.close();
console.log('wrote', out);
