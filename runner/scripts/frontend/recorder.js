// Background recorder: appends every response whose URL contains URL_FILTER to
// a JSONL log, so scenarios running as separate processes can read the traffic
// they caused (filter by timestamp >= their own start time).
// Usage: URL_FILTER=/change-logs/ node recorder.js <log.jsonl>   (run_in_background)
const fs = require('fs');
const { attach } = require('./lib');

const log = process.argv[2] || 'net.jsonl';
const filter = process.env.URL_FILTER || '/api/';

(async () => {
  const { page } = await attach();
  page.on('response', async (r) => {
    if (!r.url().includes(filter)) return;
    let body = null;
    try { body = await r.json(); } catch {}
    fs.appendFileSync(log, JSON.stringify({ t: Date.now(), status: r.status(), url: r.url(), body }) + '\n');
  });
  page.on('requestfailed', (q) => {
    if (q.url().includes(filter)) fs.appendFileSync(log, JSON.stringify({ t: Date.now(), status: 'FAILED', url: q.url() }) + '\n');
  });
  console.log(`recording ${filter} -> ${log}`);
  setInterval(() => {}, 1 << 30);
})().catch((e) => { console.log('ERR', e.message); process.exit(1); });
