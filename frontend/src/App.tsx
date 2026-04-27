import { useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  ConfigProvider,
  Grid,
  Input,
  Layout,
  Menu,
  Row,
  Segmented,
  Space,
  Spin,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  DashboardOutlined,
  DeploymentUnitOutlined,
  FileSearchOutlined,
  LockOutlined,
  PlayCircleOutlined,
  SafetyCertificateOutlined,
  ShareAltOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { getEnvelope, api, authHeader } from "./api";

const { Header, Content, Sider } = Layout;
const { Title, Text } = Typography;
const { useBreakpoint } = Grid;

type NavKey = "dashboard" | "run" | "result" | "causal" | "recommendation" | "operations";
type Role = "tenant_admin" | "ml_operator" | "viewer";
type ViewState = "idle" | "loading" | "error" | "success";

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

function canExecute(role: Role) {
  return role === "tenant_admin" || role === "ml_operator";
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
            <div>
              <Text strong>code</Text>: API_ERROR
            </div>
            <div>
              <Text strong>message</Text>: {error ?? "unknown error"}
            </div>
            <div>
              <Text strong>details</Text>: check request_id / trace_id on backend logs
            </div>
          </div>
        }
      />
    );
  }

  if (state === "idle") {
    return <Alert type="info" showIcon message="No data" description="Enter task_id and load data." />;
  }

  return null;
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
          />
        </Space.Compact>
        <Space>
          <Text type="secondary">Role</Text>
          <Segmented<Role>
            options={["tenant_admin", "ml_operator", "viewer"]}
            value={role}
            onChange={(value) => setRole(value)}
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
      <Button icon={<DashboardOutlined />} type="primary" loading={loading} onClick={fetchData}>
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
  const [algorithm, setAlgorithm] = useState("IsolationForest");
  const [taskId, setTaskId] = useState("");
  const [loading, setLoading] = useState(false);
  const executable = canExecute(role);

  const submit = async () => {
    if (!executable) {
      message.warning("Current role is read-only.");
      return;
    }
    setLoading(true);
    try {
      const payload = {
        df: [{ ts: "2026-01-01", value: 1.0 }, { ts: "2026-01-02", value: 2.0 }],
        algorithm,
        params: { n_jobs: 1, contamination: 0.1, max_samples: 2 },
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
    <Space direction="vertical" style={{ width: "100%" }}>
      <Card title="Detection Run (API-first)">
        <Space.Compact style={{ width: "100%", maxWidth: 460 }}>
          <Input value={algorithm} onChange={(e) => setAlgorithm(e.target.value)} placeholder="Algorithm" />
          <Button icon={<PlayCircleOutlined />} type="primary" onClick={submit} loading={loading} disabled={!executable}>
            Run
          </Button>
        </Space.Compact>
        <div style={{ marginTop: 16 }}>
          <Text>Last task_id: </Text>
          <Tag color="blue">{taskId || "(none)"}</Tag>
        </div>
      </Card>
      <Alert
        type={executable ? "info" : "warning"}
        showIcon
        message={executable ? "Sample execution view" : "Execution disabled"}
        description={executable ? "Upload/model forms are next extension." : "viewer role can only query data."}
      />
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
      <Card title="Task Result">
        <Space.Compact style={{ width: "100%", maxWidth: 520 }}>
          <Input placeholder="task_id" value={taskId} onChange={(e) => setTaskId(e.target.value)} />
          <Button onClick={fetchResult} icon={<FileSearchOutlined />}>Load</Button>
        </Space.Compact>
      </Card>
      <StateBlock state={state} title="Task Result" error={error} />
      {state === "success" && (
        <Card>
          <pre>{JSON.stringify(taskData, null, 2)}</pre>
        </Card>
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
      <Card title="Causal Report">
        <Space.Compact style={{ width: "100%", maxWidth: 560 }}>
          <Input placeholder="task_id" value={taskId} onChange={(e) => setTaskId(e.target.value)} />
          <Button onClick={fetchData} icon={<ShareAltOutlined />}>Load Causal</Button>
        </Space.Compact>
      </Card>
      <StateBlock state={state} title="Causal Report" error={error} />
      {state === "success" && (
        <Card>
          <pre>{JSON.stringify(data, null, 2)}</pre>
        </Card>
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
      <Card title="Action Recommendation">
        <Space.Compact style={{ width: "100%", maxWidth: 560 }}>
          <Input placeholder="task_id" value={taskId} onChange={(e) => setTaskId(e.target.value)} />
          <Button onClick={fetchData} icon={<ThunderboltOutlined />}>Load Action</Button>
        </Space.Compact>
      </Card>
      <StateBlock state={state} title="Action Recommendation" error={error} />
      {state === "success" && (
        <Card>
          <pre>{JSON.stringify(data, null, 2)}</pre>
        </Card>
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
      <Button icon={<SafetyCertificateOutlined />} onClick={refresh} type="primary">Refresh Operations</Button>
      <Tabs
        items={[
          {
            key: "quota",
            label: "Quota",
            children: (
              <Row gutter={[16, 16]}>
                <Col xs={24} md={8}><Card><Statistic title="Plan" value={quota?.plan_tier ?? "-"} /></Card></Col>
                <Col xs={24} md={8}><Card><Statistic title="Active" value={quota?.active_count ?? 0} /></Card></Col>
                <Col xs={24} md={8}><Card><Statistic title="Remaining" value={quota?.remaining_capacity ?? 0} /></Card></Col>
              </Row>
            ),
          },
          {
            key: "audit",
            label: "Audit",
            children: (
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
            ),
          },
        ]}
      />
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
              <Tag color="green">role: {activeRole}</Tag>
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
          <Menu
            mode="horizontal"
            selectedKeys={[nav]}
            items={menuItems}
            onClick={(e) => setNav(e.key as NavKey)}
          />
        </Card>
      )}
    </ConfigProvider>
  );
}

export default App;
