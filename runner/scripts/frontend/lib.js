// Attach to the manually logged-in browser over CDP (see references/frontend.md step 3).
// Run with NODE_PATH="$(npm root -g)" so the global playwright install resolves.
const { chromium } = require('playwright');

const PORT = process.env.CDP_PORT || 9222;
const HOST = process.env.APP_HOST;
if (!HOST) throw new Error('APP_HOST is not set (host of the chosen environment)');

async function attach() {
  const browser = await chromium.connectOverCDP(`http://localhost:${PORT}`, { timeout: 15000 });
  const page = browser.contexts()[0].pages().find((p) => p.url().includes(HOST));
  if (!page) throw new Error(`no tab open on ${HOST}`);
  return { browser, page };
}

// Never call browser.close() on a CDP connection: it can close the user's window.
function run(fn) {
  (async () => {
    const { page } = await attach();
    await fn(page);
    process.exit(0);
  })().catch((e) => {
    console.log('ERR', e.message.split('\n').slice(0, 12).join(' | '));
    process.exit(1);
  });
}

module.exports = { attach, run };
