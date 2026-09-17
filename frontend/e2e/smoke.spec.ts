import { expect, test } from "@playwright/test";

// Smoke coverage only: confirms each core page renders against the seeded test DB
// (backend/tests/fixtures/seed.py) with no console errors — not a full behavioral suite.
// If this fails in CI, check first whether the backend was actually reachable at API_URL.

test("home page loads the screener with no console errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Condo screener" })).toBeVisible();
  expect(errors, `console errors: ${errors.join("\n")}`).toEqual([]);
});

test("neighborhoods page renders the seeded neighborhoods", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });

  await page.goto("/neighborhoods");
  await expect(page.getByText("Neighborhood growth scores")).toBeVisible();
  // Seeded by backend/tests/fixtures/seed.py -- if these are missing, the backend likely wasn't
  // pointed at the seeded DB, not that the page itself is broken.
  await expect(page.getByText("Test Financial District")).toBeVisible();
  await expect(page.getByText("Test Williamsburg")).toBeVisible();
  expect(errors, `console errors: ${errors.join("\n")}`).toEqual([]);
});
