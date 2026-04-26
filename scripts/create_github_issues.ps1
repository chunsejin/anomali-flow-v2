param(
    [string]$Repo = "datascience-labs/anomali-flow"
)

$ErrorActionPreference = "Stop"

$issues = @(
    @(
    "[P0][main.py] Add OIDC JWT auth RequestContext and RBAC",
        @"
## Background
The current /tasks and /tasks/{task_id} endpoints are unauthenticated and there is no tenant-aware request context.

## Tasks
- Add JWT/OIDC validation dependency
- Inject RequestContext with tenant_id, actor_id, roles, request_id, and plan_tier
- Enforce RBAC for tenant_admin, ml_operator, viewer, and platform_admin

## Done When
- Unauthenticated requests return 401 and unauthorized requests return 403
- RequestContext is available across all request paths
"@
    ),
    @(
    "[P0][worker.py] Require tenant_context in Celery contract",
        @"
## Background
Current Celery task payloads do not include tenant_context, so task isolation is not guaranteed.

## Tasks
- Change run_*_workflow signature to (df, algorithm, params, tenant_context)
- Validate required tenant_context fields before execution
- Add tenant_id and request_id to execution logs

## Done When
- Tasks cannot be enqueued or executed without tenant_context
- Task results can be linked to tenant identity
"@
    ),
    @(
    "[P0][main.py+worker.py] Add Mongo repositories tenant filter and audit log",
        @"
## Background
Direct Mongo access makes tenant filter omissions likely and there is no audit logging.

## Tasks
- Introduce TaskResultRepository and AuditRepository
- Extend TaskResult and AuditEvent schemas with tenant_id and audit fields
- Require tenant_id in repository helpers

## Done When
- Raw collection access is removed outside repositories
- Audit events are written for enqueue, result read, and failure actions
"@
    ),
    @(
    "[P1][main.py] Standardize API response schema and trace_id",
        @"
## Tasks
- Add shared response fields: tenant_id, submitted_by, trace_id, policy_version
- Standardize error responses with code, message, and details
- Propagate request_id and trace_id in logs and responses

## Done When
- Success and failure responses use a consistent schema
"@
    ),
    @(
    "[P1][worker.py] Add idempotency retry policy and tenant quota",
        @"
## Tasks
- Prevent duplicate execution with idempotency keys
- Standardize retry count, backoff, and failure categories
- Add tenant concurrency and quota limits in the shared queue

## Done When
- Duplicate requests are not executed more than once
- Metrics exist to measure noisy-neighbor mitigation
"@
    ),
    @(
    "[P1][app.py] Add Streamlit auth session and role based UI guards",
        @"
## Tasks
- Attach OIDC token to API Authorization headers
- Gate UI actions by role for view-only vs execute permissions
- Handle 401 and 403 states in the UI

## Done When
- Unauthenticated users cannot execute or view restricted flows
- UI actions are limited correctly by user role
"@
    ),
    @(
    "[P2][worker.py] Draft CausalReport and ActionRecommendation pipeline",
        @"
## Tasks
- Draft CausalReport and ActionRecommendation schemas
- Define task_id and analysis_id link keys

## Done When
- Storage structures are ready for future causal analysis and recommendation APIs
"@
    ),
    @(
    "[P2][app.py] Refactor visualization into API first modules",
        @"
## Tasks
- Separate preprocessing, API calls, and visualization logic
- Refactor around API contracts to prepare for React dashboard migration

## Done When
- app.py is modularized and no longer a single large dependency point
"@
    ),
    @(
    "[P2][main.py+worker.py+app.py] Add structured logs and request correlation",
        @"
## Tasks
- Standardize JSON log format
- Add tenant_id, request_id, and task_id as shared correlation keys
- Classify failure types for dashboard and operations input

## Done When
- API, worker, and UI flows can be traced through one log chain
"@
    )
)

Write-Output "Target repo: $Repo"

foreach ($issue in $issues) {
    $title = $issue[0]
    $body = $issue[1]

    Write-Output "Creating: $title"
    gh issue create --repo $Repo --title $title --body $body
}

Write-Output "All issue creation commands completed."
