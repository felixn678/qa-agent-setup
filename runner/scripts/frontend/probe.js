// Attach to the QA browser tab and print one JSON line: where it is and whether it looks like a login page.
// Used by verify_setup.py --live and by QA preflight. Run: APP_HOST=localhost:3000 NODE_PATH="$(npm root -g)" node probe.js
const { run } = require('./lib');

run(async (page) => {
  await page.waitForTimeout(1500);
  const url = page.url();
  const title = await page.title().catch(() => '');
  const hasPassword = (await page.locator('input[type="password"]').count()) > 0;
  const loginUrl = /(login|signin|sign-in|sso|oauth|authorize|b2clogin|microsoftonline|okta|auth0)/i.test(url);
  const loginText = /(sign in|log in|login to continue|forgot password)/i.test(await page.locator('body').innerText().catch(() => ''));
  console.log(JSON.stringify({ url, title, hasPassword, loginDetected: loginUrl || hasPassword || (loginText && /login|sign/i.test(url)) }));
});
