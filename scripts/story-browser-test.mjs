import { chromium } from "playwright";
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  args: ["--no-sandbox", "--autoplay-policy=no-user-gesture-required"],
});
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1100 },
  });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(process.env.TEST_BASE_URL || "http://127.0.0.1:8000");
  await page
    .getByRole("heading", { name: "Příběhy, které ožijí a promluví." })
    .waitFor();
  const checkbox = page.getByRole("checkbox", {
    name: "Komentář, který vysvětluje děj",
  });
  assert.equal(await checkbox.isChecked(), true);
  await page
    .getByRole("button", { name: "Poslechnout mužský hlas", exact: true })
    .click();
  const audio = page.getByLabel("Ukázka mužského vypravěče");
  await audio.waitFor({ timeout: 60000 });
  await audio.evaluate(
    (el) =>
      new Promise((resolve, reject) => {
        if (el.readyState) resolve();
        else {
          el.onloadedmetadata = resolve;
          el.onerror = reject;
        }
      }),
  );
  assert.ok((await audio.evaluate((el) => el.duration)) > 1);
  await audio.evaluate((el) => el.play());
  await page.waitForTimeout(600);
  assert.ok((await audio.evaluate((el) => el.currentTime)) > 0);
  await audio.evaluate((el) => el.pause());
  await page.getByRole("button", { name: "35 sekund", exact: true }).click();
  await page
    .getByRole("button", { name: "Ukázat vzhled", exact: true })
    .click();
  await page
    .getByAltText("Skutečný 3D náhled lidí v parku")
    .waitFor({ timeout: 90000 });
  assert.equal(
    await page.locator(".story-phone img").evaluate((el) => el.naturalWidth),
    360,
  );
  await mkdir(".runtime/screenshots", { recursive: true });
  await page.screenshot({
    path: ".runtime/screenshots/story-voice-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Vygenerovat Short s hlasem", exact: true })
    .click();
  await page.waitForFunction(() =>
    ["queued", "running"].includes(
      JSON.parse(localStorage.getItem("short-story-project") || "{}").job
        ?.status,
    ),
  );
  await page.reload(); // Running jobs and inputs survive browser refresh.
  await page
    .getByRole("link", { name: "Stáhnout MP4", exact: true })
    .waitFor({ timeout: 1800000 });
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
  const result = await video.getAttribute("src");
  console.log("Generated example: " + result);
  await page.reload();
  await page.getByRole("link", { name: "Stáhnout MP4", exact: true }).waitFor();
  assert.equal(
    await page.locator(".story-phone video").getAttribute("src"),
    result,
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: ".runtime/screenshots/story-voice-mobile.png",
    fullPage: true,
  });
  assert.ok(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  );
  assert.deepEqual(errors, []);
  console.log(
    "Passed: real Czech male voice preview/playback, Blender preview, 35-second narrated MP4, refresh during/after render, download and mobile layout.",
  );
} finally {
  await browser.close();
}
