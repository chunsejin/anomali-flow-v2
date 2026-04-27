import { expect, test } from "@playwright/test";

function envelope(data: unknown) {
  return {
    tenant_id: "default",
    submitted_by: "e2e",
    trace_id: "trace-1",
    request_id: "trace-1",
    policy_version: "v1",
    data,
    error: null,
  };
}

test.beforeEach(async ({ page }) => {
  await page.route("**/tasks", async (route) => {
    if (route.request().method() !== "POST") {
      await route.fallback();
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(envelope({ task_id: "demo-task", status: "PENDING" })),
    });
  });

  await page.route("**/tasks/demo-task", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(
        envelope({
          task_id: "demo-task",
          status: "SUCCESS",
          result: { outlier_count: 3, anomaly_ratio: 0.15 },
        }),
      ),
    });
  });

  await page.route("**/tasks/demo-task/causal-report", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(
        envelope({
          task_id: "demo-task",
          causal_report: {
            analysis_id: "causal-1",
            treatment: "discount",
            outcome: "conversion",
            effect_size: 0.22,
            refutation_result: "passed",
          },
        }),
      ),
    });
  });

  await page.route("**/tasks/demo-task/action-recommendation", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(
        envelope({
          task_id: "demo-task",
          action_recommendation: {
            recommendation_id: "rec-1",
            scenario: "increase_budget",
            expected_uplift: 0.11,
            risk_level: "medium",
            priority: "high",
          },
        }),
      ),
    });
  });

  await page.route("**/operations/quota", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(
        envelope({
          plan_tier: "standard",
          active_count: 1,
          max_concurrency: 2,
          remaining_capacity: 1,
        }),
      ),
    });
  });

  await page.route("**/operations/audit-events**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(
        envelope({
          count: 1,
          events: [
            {
              timestamp: "2026-04-27T00:00:00Z",
              actor_id: "e2e",
              action: "task.enqueue",
              resource_type: "task",
              result: "success",
              request_id: "trace-1",
            },
          ],
        }),
      ),
    });
  });

  await page.route("**/dashboard/summary", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(
        envelope({
          metrics: { total: 10, success: 8, failures: 2, success_rate: 80, by_status: { SUCCESS: 8, FAILURE: 2 } },
          active_tasks: 1,
          recent_tasks: [{ task_id: "demo-task", status: "SUCCESS", algorithm: "IsolationForest", updated_at: "2026-04-27T00:00:00Z" }],
        }),
      ),
    });
  });

  await page.goto("/");
});

test("viewer role cannot run detection", async ({ page }) => {
  await page.getByRole("menuitem", { name: "Detection Run" }).click();
  await page.locator(".ant-segmented-item").filter({ hasText: "viewer" }).first().click();

  const runButton = page.getByTestId("run-submit");
  await expect(runButton).toBeDisabled();
});

test("task flow cards load for result/causal/recommendation", async ({ page }) => {
  await page.getByRole("menuitem", { name: "Detection Run" }).click();

  await page.locator('input[type="file"]').setInputFiles({
    name: "input.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("ts,value\n2026-01-01,1.0\n2026-01-02,1.2\n"),
  });

  await page.getByTestId("run-submit").click();
  await expect(page.getByText("task_id: demo-task")).toBeVisible();

  await page.getByRole("menuitem", { name: "Task Result" }).click();
  await page.getByTestId("task-id-input").fill("demo-task");
  await page.getByTestId("task-load").click();
  await expect(page.getByText("Task Summary")).toBeVisible();
  await expect(page.getByText("SUCCESS").first()).toBeVisible();

  await page.getByRole("menuitem", { name: "Causal Report" }).click();
  await page.getByTestId("causal-task-id-input").fill("demo-task");
  await page.getByTestId("causal-load").click();
  await expect(page.getByText("Causal Summary")).toBeVisible();
  await expect(page.getByText("discount")).toBeVisible();

  await page.getByRole("menuitem", { name: "Recommendation" }).click();
  await page.getByTestId("action-task-id-input").fill("demo-task");
  await page.getByTestId("action-load").click();
  await expect(page.getByText("Recommendation Summary")).toBeVisible();
  await expect(page.getByText("increase_budget")).toBeVisible();
});
