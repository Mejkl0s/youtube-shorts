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
    .getByRole("heading", { name: "Stories that move and speak." })
    .waitFor();
  const checkbox = page.getByRole("checkbox", {
    name: "Narrate the story",
  });
  assert.equal(await checkbox.isChecked(), true);
  await page
    .getByRole("button", { name: "Preview male voice", exact: true })
    .click();
  const audio = page.getByLabel("Male narrator preview");
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
  await page.getByLabel("Optional duration", {exact: true}).fill("35");
  await page
    .getByRole("button", { name: "Preview the scene", exact: true })
    .click();
  await page
    .getByAltText("Actual 3D scene preview")
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
    .getByRole("button", { name: "Generate Short with narration", exact: true })
    .click();
  await page.waitForFunction(() =>
    ["queued", "running"].includes(
      JSON.parse(localStorage.getItem("short-story-project-v2-en") || "{}").job
        ?.status,
    ),
  );
  await page.reload(); // Running jobs and inputs survive browser refresh.
  await page
    .getByRole("link", { name: "Download MP4", exact: true })
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
  await page.getByRole("link", { name: "Download MP4", exact: true }).waitFor();
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
    "Passed: real English male voice preview/playback, Blender preview, 35-second narrated MP4, refresh during/after render, download and mobile layout.",
  );
} finally {
  await browser.close();
}
