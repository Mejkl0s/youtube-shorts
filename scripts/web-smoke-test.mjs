import { chromium } from "playwright";
import assert from "node:assert/strict";
const base = process.env.TEST_BASE_URL || "http://127.0.0.1:18080";
const username = process.env.TEST_USERNAME || "owner";
const password = process.env.TEST_PASSWORD;
if (!password)
  throw new Error(
    "Set TEST_PASSWORD for the protected production web smoke test.",
  );
assert.equal((await fetch(base + "/api/health")).status, 200);
assert.equal((await fetch(base + "/")).status, 401);
assert.equal((await fetch(base + "/examples/story-narrated.mp4")).status, 401);
const headers = {
  Authorization:
    "Basic " + Buffer.from(username + ":" + password).toString("base64"),
  Range: "bytes=0-127",
};
const media = await fetch(base + "/examples/story-narrated.mp4", { headers });
assert.equal(media.status, 206);
assert.match(media.headers.get("content-range"), /^bytes 0-127\//);
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  args: ["--no-sandbox", "--autoplay-policy=no-user-gesture-required"],
});
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
    httpCredentials: { username, password },
  });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(base);
  await page
    .getByRole("button", {
      name: "Přehrát hotovou ukázku s hlasem",
      exact: true,
    })
    .click();
  const video = page.locator(".story-phone video");
  await video.evaluate(
    (el) =>
      new Promise((resolve, reject) => {
        if (el.readyState) resolve();
        else {
          el.onloadedmetadata = resolve;
          el.onerror = reject;
        }
      }),
  );
  assert.equal(await video.evaluate((el) => el.duration), 35);
  assert.equal(await video.evaluate((el) => el.muted), false);
  await video.evaluate((el) => el.play());
  await page.waitForTimeout(1000);
  assert.ok((await video.evaluate((el) => el.currentTime)) > 0);
  const caps = await (
    await page.request.get(base + "/api/story/capabilities")
  ).json();
  assert.equal(caps.local, true);
  assert.equal(caps.blender, true);
  await page
    .getByRole("button", { name: "Poslechnout mužský hlas", exact: true })
    .click();
  await page
    .getByLabel("Ukázka mužského vypravěče")
    .waitFor({ timeout: 30000 });
  await page.setViewportSize({ width: 390, height: 844 });
  assert.ok(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  );
  assert.deepEqual(errors, []);
  console.log(
    "Production web passed: password protection, authenticated video range/download, actual bundled movie playback with sound enabled, speech preview, renderer availability and mobile layout.",
  );
} finally {
  await browser.close();
}
