import { useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Collapse,
  ConfigProvider,
  Descriptions,
  Grid,
  Input,
  InputNumber,
  Layout,
  Menu,
  Row,
  Segmented,
  Select,
  Space,
  Spin,
  Statistic,
  Switch,
  Table,
  Tag,
  Typography,
  Upload,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  DashboardOutlined,
  DeploymentUnitOutlined,
  FileSearchOutlined,
  InboxOutlined,
  LockOutlined,
  PlayCircleOutlined,
  SafetyCertificateOutlined,
  ShareAltOutlined,
  ThunderboltOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import { getEnvelope, api, authHeader } from "./api";

const { Header, Content, Sider } = Layout;
const { Title, Text } = Typography;
const { useBreakpoint } = Grid;
const { Dragger } = Upload;

type NavKey = "dashboard" | "run" | "result" | "causal" | "recommendation" | "operations";
type Role = "tenant_admin" | "ml_operator" | "viewer";
type ViewState = "idle" | "loading" | "error" | "success";
type DataType = "time_series" | "categorical" | "numerical";

type DashboardSummary = {
  metrics: {
    total: number;
    success: number;
    failures: number;
    success_rate: number;
    by_status: Record<string, number>;
  };
  active_tasks: number;
  recent_tasks: Array<Record<string, unknown>>;
};

type TaskData = {
  task_id: string;
  status: string;
  result?: Record<string, unknown> | string;
};

type AuditData = {
  count: number;
  events: Array<Record<string, unknown>>;
};

type QuotaData = {
  plan_tier: string;
  active_count: number;
  max_concurrency: number;
  remaining_capacity: number;
};

type ParamSpec = {
  key: string;
  label: string;
  type: "number" | "text" | "boolean";
  defaultValue: number | string | boolean;
  min?: number;
  max?: number;
  step?: number;
};

const MODEL_PARAM_SPECS: Record<string, ParamSpec[]> = {
  IsolationForest: [
    { key: "contamination", label: "Contamination", type: "number", defaultValue: 0.1, min: 0.001, max: 0.5, step: 0.001 },
    { key: "max_samples", label: "Max Samples", type: "number", defaultValue: 256, min: 2, max: 10000, step: 1 },
    { key: "n_jobs", label: "n_jobs", type: "number", defaultValue: 1, min: 1, max: 16, step: 1 },
  ],
  DBSCAN: [
    { key: "eps", label: "eps", type: "number", defaultValue: 0.5, min: 0.001, max: 10, step: 0.001 },
    { key: "min_samples", label: "min_samples", type: "number", defaultValue: 5, min: 1, max: 500, step: 1 },
  ],
  KMeans: [
    { key: "n_clusters", label: "n_clusters", type: "number", defaultValue: 3, min: 2, max: 64, step: 1 },
    { key: "max_iter", label: "max_iter", type: "number", defaultValue: 300, min: 10, max: 5000, step: 1 },
    { key: "random_state", label: "random_state", type: "number", defaultValue: 42, min: 0, max: 100000, step: 1 },
  ],
  LOF: [
    { key: "n_neighbors", label: "n_neighbors", type: "number", defaultValue: 20, min: 2, max: 500, step: 1 },
    { key: "contamination", label: "Contamination", type: "number", defaultValue: 0.1, min: 0.001, max: 0.5, step: 0.001 },
    { key: "novelty", label: "novelty", type: "boolean", defaultValue: false },
  ],
};

function canExecute(role: Role) {
  return role === "tenant_admin" || role === "ml_operator";
}

function safeJsonStringify(value: unknown) {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function parseCsvToRecords(content: string): Array<Record<string, unknown>> {
  const lines = content
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (lines.length < 2) return [];

  const headers = lines[0].split(",").map((h) => h.trim());
  const rows = lines.slice(1);

  return rows.map((row) => {
    const values = row.split(",").map((v) => v.trim());
    const record: Record<string, unknown> = {};
    headers.forEach((header, idx) => {
      const raw = values[idx] ?? "";
      if (raw === "") {
        record[header] = "";
        return;
      }
      const asNumber = Number(raw);
      record[header] = Number.isNaN(asNumber) ? raw : asNumber;
    });
    return record;
  });
}

function decodeRolesFromToken(token: string): Role[] {
  if (!token || !token.includes(".")) return [];
  try {
    const payload = token.split(".")[1];
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const decoded = JSON.parse(atob(normalized));
    const candidates = [
      ...(Array.isArray(decoded.roles) ? decoded.roles : []),
      ...(Array.isArray(decoded.role) ? decoded.role : []),
      typeof decoded.role === "string" ? decoded.role : "",
      ...(Array.isArray(decoded["https://anomali-flow/roles"])
        ? decoded["https://anomali-flow/roles"]
        : []),
    ]
      .filter(Boolean)
      .map((v: unknown) => String(v));

    const roles: Role[] = [];
    for (const value of candidates) {
      if (value === "tenant_admin" || value === "ml_operator" || value === "viewer") {
        roles.push(value);
      }
    }
    return roles;
  } catch {
    return [];
  }
}

function pickActiveRole(manual: Role, token: string): Role {
  const tokenRoles = decodeRolesFromToken(token);
  if (tokenRoles.includes("tenant_admin")) return "tenant_admin";
  if (tokenRoles.includes("ml_operator")) return "ml_operator";
  if (tokenRoles.includes("viewer")) return "viewer";
  return manual;
}

function StateBlock({
  state,
  title,
  error,
}: {
  state: ViewState;
  title: string;
  error?: string | null;
}) {
  if (state === "loading") {
    return (
      <Card>
        <Space>
          <Spin size="small" />
          <Text>{title} loading...</Text>
        </Space>
      </Card>
    );
  }

  if (state === "error") {
    return (
      <Alert
        type="error"
        showIcon
        message="Request failed"
        description={
          <div>
            <div><Text strong>code</Text>: API_ERROR</div>
            <div><Text strong>message</Text>: {error ?? "unknown error"}</div>
            <div><Text strong>details</Text>: check request_id / trace_id on backend logs</div>
          </div>
        }
      />
    );
  }

  if (state === "idle") {
    return <Alert type="info" showIcon message="No data" description="Input task_id and load data." />;
  }

  return null;
}

function JsonPanel({ title, value }: { title: string; value: unknown }) {
  return (
    <Collapse
      items={[
        {
          key: "raw",
          label: title,
          children: <pre>{safeJsonStringify(value)}</pre>,
        },
      ]}
    />
  );
}

function SummaryCard({
  title,
  rows,
}: {
  title: string;
  rows: Array<{ label: string; value: unknown }>;
}) {
  return (
    <Card title={title}>
      <Descriptions size="small" column={1}>
        {rows.map((row) => (
          <Descriptions.Item key={row.label} label={row.label}>
            {String(row.value ?? "-")}
          </Descriptions.Item>
        ))}
      </Descriptions>
    </Card>
  );
}

function AuthPanel({
  token,
  setToken,
  role,
  setRole,
}: {
  token: string;
  setToken: (v: string) => void;
  role: Role;
  setRole: (v: Role) => void;
}) {
  return (
    <Card size="small" title={<Space><LockOutlined />Auth Session</Space>}>
      <Space direction="vertical" style={{ width: "100%" }}>
        <Space.Compact style={{ width: "100%" }}>
          <Input.Password
            placeholder="Bearer token"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            data-testid="auth-token-input"
          />
        </Space.Compact>
        <Space>
          <Text type="secondary">Role</Text>
          <Segmented<Role>
            options={["tenant_admin", "ml_operator", "viewer"]}
            value={role}
            onChange={(value) => setRole(value)}
            data-testid="auth-role-segment"
          />
        </Space>
        <Text type="secondary">When token has roles claim, token role takes precedence.</Text>
      </Space>
    </Card>
  );
}

function DashboardView({ token }: { token: string }) {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const env = await getEnvelope<DashboardSummary>("/dashboard/summary", token || undefined);
      if (env.error) throw new Error(env.error.message);
      setData(env.data);
    } catch (err) {
      message.error(String(err));
    } finally {
      setLoading(false);
    }
  };

  const cols: ColumnsType<Record<string, unknown>> = useMemo(
    () => [
      { title: "task_id", dataIndex: "task_id", key: "task_id" },
      { title: "status", dataIndex: "status", key: "status" },
      { title: "algorithm", dataIndex: "algorithm", key: "algorithm" },
      { title: "updated_at", dataIndex: "updated_at", key: "updated_at" },
    ],
    [],
  );

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Button icon={<DashboardOutlined />} type="primary" loading={loading} onClick={fetchData} data-testid="dashboard-refresh">
        Refresh Dashboard
      </Button>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={12} xl={6}><Card><Statistic title="Active" value={data?.active_tasks ?? 0} /></Card></Col>
        <Col xs={24} md={12} xl={6}><Card><Statistic title="Total(24h)" value={data?.metrics.total ?? 0} /></Card></Col>
        <Col xs={24} md={12} xl={6}><Card><Statistic title="Success Rate" suffix="%" value={data?.metrics.success_rate ?? 0} /></Card></Col>
        <Col xs={24} md={12} xl={6}><Card><Statistic title="Failures" value={data?.metrics.failures ?? 0} /></Card></Col>
      </Row>
      <Card title="Recent Tasks">
        <Table
          size="small"
          rowKey={(row) => String(row.task_id ?? crypto.randomUUID())}
          columns={cols}
          dataSource={data?.recent_tasks ?? []}
          pagination={{ pageSize: 8 }}
          scroll={{ x: 760 }}
        />
      </Card>
    </Space>
  );
}

function DetectionRunView({ token, role }: { token: string; role: Role }) {
  const [dataType, setDataType] = useState<DataType>("time_series");
  const [algorithm, setAlgorithm] = useState("IsolationForest");
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(false);
  const [taskId, setTaskId] = useState("");

  const executable = canExecute(role);

  const initialParams = useMemo(() => {
    const specs = MODEL_PARAM_SPECS[algorithm] ?? [];
    const result: Record<string, unknown> = {};
    for (const spec of specs) result[spec.key] = spec.defaultValue;
    result.data_type = dataType;
    return result;
  }, [algorithm, dataType]);

  const [params, setParams] = useState<Record<string, unknown>>(initialParams);

  const modelSpecs = MODEL_PARAM_SPECS[algorithm] ?? [];

  const updateParam = (key: string, value: unknown) => {
    setParams((prev) => ({ ...prev, [key]: value }));
  };

  const onAlgorithmChange = (value: string) => {
    setAlgorithm(value);
    const defaults: Record<string, unknown> = { data_type: dataType };
    for (const spec of MODEL_PARAM_SPECS[value] ?? []) defaults[spec.key] = spec.defaultValue;
    setParams(defaults);
  };

  const onDataTypeChange = (value: DataType) => {
    setDataType(value);
    setParams((prev) => ({ ...prev, data_type: value }));
  };

  const onUpload = async (file: File) => {
    const text = await file.text();
    const parsedRows = parseCsvToRecords(text);
    setRows(parsedRows);
    message.success(`Loaded ${parsedRows.length} rows from ${file.name}`);
    return false;
  };

  const downloadSample = () => {
    const sample = "ts,value,category\n2026-01-01,1.0,A\n2026-01-02,2.3,B\n2026-01-03,0.7,A\n";
    const blob = new Blob([sample], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "sample_detection_input.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const submit = async () => {
    if (!executable) {
      message.warning("Current role is read-only.");
      return;
    }
    if (rows.length === 0) {
      message.warning("Upload CSV first.");
      return;
    }

    setLoading(true);
    try {
      const payload = {
        df: rows,
        algorithm,
        params,
      };
      const res = await api.post("/tasks", payload, {
        headers: {
          ...authHeader(token || undefined),
          "X-Request-Id": crypto.randomUUID(),
        },
      });
      const createdTaskId = res.data?.data?.task_id;
      setTaskId(createdTaskId ?? "");
      message.success(`Task submitted: ${createdTaskId}`);
    } catch (err) {
      message.error(String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Card title="Detection Run" data-testid="run-card">
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <Row gutter={[16, 16]}>
            <Col xs={24} md={12}>
              <Text>Data Type</Text>
              <Segmented<DataType>
                block
                value={dataType}
                onChange={onDataTypeChange}
                options={["time_series", "categorical", "numerical"]}
              />
            </Col>
            <Col xs={24} md={12}>
              <Text>Model</Text>
              <Select
                style={{ width: "100%" }}
                value={algorithm}
                onChange={onAlgorithmChange}
                options={Object.keys(MODEL_PARAM_SPECS).map((v) => ({ label: v, value: v }))}
              />
            </Col>
          </Row>

          <Dragger
            beforeUpload={onUpload}
            maxCount={1}
            accept=".csv"
            showUploadList={{ showRemoveIcon: false }}
            data-testid="run-upload"
          >
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">Click or drag CSV file to this area</p>
            <p className="ant-upload-hint">Detection input CSV required</p>
          </Dragger>

          <Space>
            <Button icon={<UploadOutlined />} onClick={downloadSample}>Download Sample CSV</Button>
            <Tag color={rows.length > 0 ? "green" : "default"}>rows: {rows.length}</Tag>
          </Space>

          <Card size="small" title="Model Parameters">
            <Row gutter={[12, 12]}>
              {modelSpecs.map((spec) => (
                <Col xs={24} md={12} key={spec.key}>
                  <Space direction="vertical" style={{ width: "100%" }} size={4}>
                    <Text type="secondary">{spec.label}</Text>
                    {spec.type === "number" && (
                      <InputNumber
                        style={{ width: "100%" }}
                        value={Number(params[spec.key] ?? spec.defaultValue)}
                        min={spec.min}
                        max={spec.max}
                        step={spec.step}
                        onChange={(value) => updateParam(spec.key, value ?? spec.defaultValue)}
                      />
                    )}
                    {spec.type === "text" && (
                      <Input
                        value={String(params[spec.key] ?? spec.defaultValue)}
                        onChange={(event) => updateParam(spec.key, event.target.value)}
                      />
                    )}
                    {spec.type === "boolean" && (
                      <Switch
                        checked={Boolean(params[spec.key] ?? spec.defaultValue)}
                        onChange={(checked) => updateParam(spec.key, checked)}
                      />
                    )}
                  </Space>
                </Col>
              ))}
            </Row>
          </Card>

          <Space>
            <Button
              icon={<PlayCircleOutlined />}
              type="primary"
              onClick={submit}
              loading={loading}
              disabled={!executable}
              data-testid="run-submit"
            >
              Run Workflow
            </Button>
            <Tag color={executable ? "blue" : "orange"}>role: {role}</Tag>
            <Tag color="purple">task_id: {taskId || "(none)"}</Tag>
          </Space>
        </Space>
      </Card>
    </Space>
  );
}

function TaskResultView({ token }: { token: string }) {
  const [taskId, setTaskId] = useState("");
  const [taskData, setTaskData] = useState<TaskData | null>(null);
  const [state, setState] = useState<ViewState>("idle");
  const [error, setError] = useState<string | null>(null);

  const fetchResult = async () => {
    if (!taskId) return;
    setState("loading");
    setError(null);
    try {
      const env = await getEnvelope<TaskData>(`/tasks/${taskId}`, token || undefined);
      if (env.error) throw new Error(env.error.message);
      setTaskData(env.data);
      setState("success");
    } catch (err) {
      const msg = String(err);
      setError(msg);
      setState("error");
      message.error(msg);
    }
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <Card title="Task Result" data-testid="task-result-card">
        <Space.Compact style={{ width: "100%", maxWidth: 520 }}>
          <Input placeholder="task_id" value={taskId} onChange={(e) => setTaskId(e.target.value)} data-testid="task-id-input" />
          <Button onClick={fetchResult} icon={<FileSearchOutlined />} data-testid="task-load">Load</Button>
        </Space.Compact>
      </Card>
      <StateBlock state={state} title="Task Result" error={error} />
      {state === "success" && taskData && (
        <Space direction="vertical" style={{ width: "100%" }}>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={12}>
              <SummaryCard
                title="Task Summary"
                rows={[
                  { label: "task_id", value: taskData.task_id },
                  { label: "status", value: taskData.status },
                  { label: "result_type", value: typeof taskData.result },
                ]}
              />
            </Col>
            <Col xs={24} md={12}>
              <Card title="Status">
                <Statistic title="Current" value={taskData.status} />
                <Tag color={taskData.status === "SUCCESS" ? "green" : taskData.status === "FAILURE" ? "red" : "blue"}>
                  {taskData.status}
                </Tag>
              </Card>
            </Col>
          </Row>
          <JsonPanel title="Raw Task JSON" value={taskData} />
        </Space>
      )}
    </Space>
  );
}

function CausalReportView({ token }: { token: string }) {
  const [taskId, setTaskId] = useState("");
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [state, setState] = useState<ViewState>("idle");
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!taskId) return;
    setState("loading");
    setError(null);
    try {
      const env = await getEnvelope<{ causal_report: Record<string, unknown> }>(
        `/tasks/${taskId}/causal-report`,
        token || undefined,
      );
      if (env.error) throw new Error(env.error.message);
      setData(env.data?.causal_report ?? null);
      setState("success");
    } catch (err) {
      const msg = String(err);
      setError(msg);
      setState("error");
      message.error(msg);
    }
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <Card title="Causal Report" data-testid="causal-card">
        <Space.Compact style={{ width: "100%", maxWidth: 560 }}>
          <Input
            placeholder="task_id"
            value={taskId}
            onChange={(e) => setTaskId(e.target.value)}
            data-testid="causal-task-id-input"
          />
          <Button onClick={fetchData} icon={<ShareAltOutlined />} data-testid="causal-load">Load Causal</Button>
        </Space.Compact>
      </Card>
      <StateBlock state={state} title="Causal Report" error={error} />
      {state === "success" && data && (
        <Space direction="vertical" style={{ width: "100%" }}>
          <SummaryCard
            title="Causal Summary"
            rows={[
              { label: "analysis_id", value: data.analysis_id },
              { label: "treatment", value: data.treatment },
              { label: "outcome", value: data.outcome },
              { label: "effect_size", value: data.effect_size },
              { label: "refutation_result", value: data.refutation_result },
            ]}
          />
          <JsonPanel title="Raw Causal JSON" value={data} />
        </Space>
      )}
    </Space>
  );
}

function RecommendationView({ token }: { token: string }) {
  const [taskId, setTaskId] = useState("");
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [state, setState] = useState<ViewState>("idle");
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!taskId) return;
    setState("loading");
    setError(null);
    try {
      const env = await getEnvelope<{ action_recommendation: Record<string, unknown> }>(
        `/tasks/${taskId}/action-recommendation`,
        token || undefined,
      );
      if (env.error) throw new Error(env.error.message);
      setData(env.data?.action_recommendation ?? null);
      setState("success");
    } catch (err) {
      const msg = String(err);
      setError(msg);
      setState("error");
      message.error(msg);
    }
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <Card title="Action Recommendation" data-testid="action-card">
        <Space.Compact style={{ width: "100%", maxWidth: 560 }}>
          <Input
            placeholder="task_id"
            value={taskId}
            onChange={(e) => setTaskId(e.target.value)}
            data-testid="action-task-id-input"
          />
          <Button onClick={fetchData} icon={<ThunderboltOutlined />} data-testid="action-load">Load Action</Button>
        </Space.Compact>
      </Card>
      <StateBlock state={state} title="Action Recommendation" error={error} />
      {state === "success" && data && (
        <Space direction="vertical" style={{ width: "100%" }}>
          <SummaryCard
            title="Recommendation Summary"
            rows={[
              { label: "recommendation_id", value: data.recommendation_id },
              { label: "scenario", value: data.scenario },
              { label: "expected_uplift", value: data.expected_uplift },
              { label: "risk_level", value: data.risk_level },
              { label: "priority", value: data.priority },
            ]}
          />
          <JsonPanel title="Raw Recommendation JSON" value={data} />
        </Space>
      )}
    </Space>
  );
}

function OperationsView({ token }: { token: string }) {
  const [quota, setQuota] = useState<QuotaData | null>(null);
  const [audit, setAudit] = useState<AuditData | null>(null);

  const refresh = async () => {
    try {
      const [q, a] = await Promise.all([
        getEnvelope<QuotaData>("/operations/quota", token || undefined),
        getEnvelope<AuditData>("/operations/audit-events", token || undefined, { limit: 50 }),
      ]);
      if (q.error) throw new Error(q.error.message);
      if (a.error) throw new Error(a.error.message);
      setQuota(q.data);
      setAudit(a.data);
    } catch (err) {
      message.error(String(err));
    }
  };

  const auditCols: ColumnsType<Record<string, unknown>> = [
    { title: "timestamp", dataIndex: "timestamp", key: "timestamp" },
    { title: "actor_id", dataIndex: "actor_id", key: "actor_id" },
    { title: "action", dataIndex: "action", key: "action" },
    { title: "resource_type", dataIndex: "resource_type", key: "resource_type" },
    { title: "result", dataIndex: "result", key: "result" },
  ];

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <Button icon={<SafetyCertificateOutlined />} onClick={refresh} type="primary" data-testid="operations-refresh">Refresh Operations</Button>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}><Card><Statistic title="Plan" value={quota?.plan_tier ?? "-"} /></Card></Col>
        <Col xs={24} md={8}><Card><Statistic title="Active" value={quota?.active_count ?? 0} /></Card></Col>
        <Col xs={24} md={8}><Card><Statistic title="Remaining" value={quota?.remaining_capacity ?? 0} /></Card></Col>
      </Row>
      <Card title="Audit Events">
        <Table
          size="small"
          rowKey={(row) => String(row.request_id ?? crypto.randomUUID())}
          columns={auditCols}
          dataSource={audit?.events ?? []}
          pagination={{ pageSize: 10 }}
          scroll={{ x: 760 }}
        />
      </Card>
    </Space>
  );
}

function App() {
  const screens = useBreakpoint();
  const isMobile = !screens.lg;
  const [collapsed, setCollapsed] = useState(false);
  const [token, setToken] = useState("");
  const [manualRole, setManualRole] = useState<Role>("tenant_admin");
  const [nav, setNav] = useState<NavKey>("dashboard");

  const activeRole = useMemo(() => pickActiveRole(manualRole, token), [manualRole, token]);

  const menuItems = [
    { key: "dashboard", icon: <DashboardOutlined />, label: "Dashboard" },
    { key: "run", icon: <PlayCircleOutlined />, label: "Detection Run" },
    { key: "result", icon: <FileSearchOutlined />, label: "Task Result" },
    { key: "causal", icon: <ShareAltOutlined />, label: "Causal Report" },
    { key: "recommendation", icon: <ThunderboltOutlined />, label: "Recommendation" },
    { key: "operations", icon: <DeploymentUnitOutlined />, label: "Operations" },
  ];

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: "#0B6E4F",
          borderRadius: 10,
        },
      }}
    >
      <Layout style={{ minHeight: "100vh" }}>
        {!isMobile && (
          <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed} width={240}>
            <div style={{ color: "white", padding: 16, fontWeight: 700 }}>AnomaliFlow</div>
            <Menu
              theme="dark"
              mode="inline"
              selectedKeys={[nav]}
              items={menuItems}
              onClick={(e) => setNav(e.key as NavKey)}
            />
          </Sider>
        )}
        <Layout>
          <Header style={{ background: "#fff", padding: "0 16px" }}>
            <Space style={{ display: "flex", justifyContent: "space-between", width: "100%" }}>
              <Title level={4} style={{ margin: "14px 0" }}>Enterprise Dashboard</Title>
              <Tag color="green" data-testid="active-role">role: {activeRole}</Tag>
            </Space>
          </Header>
          <Content style={{ margin: 16, paddingBottom: isMobile ? 64 : 0 }}>
            <Space direction="vertical" style={{ width: "100%" }} size="large">
              <AuthPanel token={token} setToken={setToken} role={manualRole} setRole={setManualRole} />
              {nav === "dashboard" && <DashboardView token={token} />}
              {nav === "run" && <DetectionRunView token={token} role={activeRole} />}
              {nav === "result" && <TaskResultView token={token} />}
              {nav === "causal" && <CausalReportView token={token} />}
              {nav === "recommendation" && <RecommendationView token={token} />}
              {nav === "operations" && <OperationsView token={token} />}
            </Space>
          </Content>
        </Layout>
      </Layout>

      {isMobile && (
        <Card className="mobile-bottom-nav" bodyStyle={{ padding: 8 }}>
          <Segmented<NavKey>
            block
            value={nav}
            onChange={(v) => setNav(v)}
            options={[
              { label: "Dash", value: "dashboard" },
              { label: "Run", value: "run" },
              { label: "Result", value: "result" },
              { label: "Causal", value: "causal" },
              { label: "Action", value: "recommendation" },
              { label: "Ops", value: "operations" },
            ]}
          />
        </Card>
      )}
    </ConfigProvider>
  );
}

export default App;
