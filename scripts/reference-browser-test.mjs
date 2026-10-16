// External downloading is replaced with a prepared real-video fixture; all frame,
// reference persistence, UI, Blender style application and media requests are real.
import { chromium } from "playwright";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
const id = (await readFile(".runtime/reference-check-id", "utf8")).trim();
const base = process.env.TEST_BASE_URL || "http://127.0.0.1:8000";
const browser = await chromium.launch({
  executablePath: "/usr/bin/chromium",
  args: ["--no-sandbox"],
});
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1100 },
  });
  await page.goto(base);
  assert.equal(await page.locator("html").getAttribute("lang"), "en");
  await page
    .getByLabel("Reference video URL")
    .fill("https://127.0.0.1/private.mp4");
  await page
    .getByRole("button", { name: "Import and analyze reference", exact: true })
    .click();
  await page
    .getByRole("alert")
    .filter({ hasText: "Use a public YouTube" })
    .waitFor();
  await page.route("**/api/story/references", async (route) => {
    assert.equal(
      route.request().postDataJSON().url,
      "https://youtu.be/abcdefghijk",
    );
    assert.equal(route.request().postDataJSON().mode, "basic");
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        id,
        status: "queued",
        kind: "reference",
        progress: 0,
        message: "Fixture queued…",
      }),
    });
  });
  await page
    .getByLabel("Reference video URL")
    .fill("https://youtu.be/abcdefghijk");
  await page
    .getByRole("button", { name: "Import and analyze reference", exact: true })
    .click();
  await page
    .getByText("Basic visual reference · applied", { exact: true })
    .waitFor();
  await page.waitForFunction(() => {const images = [...document.querySelectorAll('.story-reference-frames img')]; return images.length === 3 && images.every(img => img.complete && img.naturalWidth > 0);});
  for (let i = 1; i <= 3; i++)
    assert.equal(
      await page
        .getByAltText("Actual reference frame " + i)
        .evaluate((el) => el.complete && el.naturalWidth > 0),
      true,
    );
  await page.unroute("**/api/story/references");
  const sent = page.waitForRequest(
    (r) => r.url().endsWith("/api/story/generate") && r.method() === "POST",
  );
  await page
    .getByRole("button", { name: "Preview the scene", exact: true })
    .click();
  const body = (await sent).postDataJSON();
  assert.equal(body.reference_id, id);
  await page
    .getByAltText("Actual 3D scene preview")
    .waitFor({ timeout: 120000 });
  assert.equal(
    await page
      .getByAltText("Actual 3D scene preview")
      .evaluate((el) => el.naturalWidth),
    360,
  );
  await page.screenshot({
    path: ".runtime/screenshots/reference-applied.png",
    fullPage: true,
  });
  await page.reload();
  await page
    .getByText("Basic visual reference · applied", { exact: true })
    .waitFor();
  await page
    .getByRole("button", { name: "Remove reference", exact: true })
    .click();
  assert.equal(await page.locator(".story-reference").count(), 0);
  console.log(
    "Passed: URL validation, real sampled reference images, style persistence, real Blender preview using the reference, refresh and removal. External video download alone used a fixture.",
  );
} finally {
  await browser.close();
}
