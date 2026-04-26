import { useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  ConfigProvider,
  Input,
  Layout,
  Menu,
  Row,
  Space,
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
} from "@ant-design/icons";
import { getEnvelope, api, authHeader } from "./api";

const { Header, Content, Sider } = Layout;
const { Title, Text } = Typography;

type NavKey = "dashboard" | "run" | "result" | "operations";

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

function AuthPanel({ token, setToken }: { token: string; setToken: (v: string) => void }) {
  return (
    <Card size="small" title={<Space><LockOutlined />Auth Session</Space>}>
      <Space.Compact style={{ width: "100%" }}>
        <Input.Password
          placeholder="Bearer token"
          value={token}
          onChange={(e) => setToken(e.target.value)}
        />
      </Space.Compact>
      <Text type="secondary">토큰이 없으면 AUTH_ENABLED=false 개발 모드에서만 동작합니다.</Text>
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
      <Space>
        <Button icon={<DashboardOutlined />} type="primary" loading={loading} onClick={fetchData}>
          Refresh Dashboard
        </Button>
      </Space>
      <Row gutter={16}>
        <Col span={6}><Card><Statistic title="Active" value={data?.active_tasks ?? 0} /></Card></Col>
        <Col span={6}><Card><Statistic title="Total(24h)" value={data?.metrics.total ?? 0} /></Card></Col>
        <Col span={6}><Card><Statistic title="Success Rate" suffix="%" value={data?.metrics.success_rate ?? 0} /></Card></Col>
        <Col span={6}><Card><Statistic title="Failures" value={data?.metrics.failures ?? 0} /></Card></Col>
      </Row>
      <Card title="Recent Tasks">
        <Table
          size="small"
          rowKey={(row) => String(row.task_id ?? crypto.randomUUID())}
          columns={cols}
          dataSource={data?.recent_tasks ?? []}
          pagination={{ pageSize: 8 }}
        />
      </Card>
    </Space>
  );
}

function DetectionRunView({ token }: { token: string }) {
  const [algorithm, setAlgorithm] = useState("IsolationForest");
  const [taskId, setTaskId] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
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
        <Space.Compact style={{ width: 360 }}>
          <Input value={algorithm} onChange={(e) => setAlgorithm(e.target.value)} placeholder="Algorithm" />
          <Button icon={<PlayCircleOutlined />} type="primary" onClick={submit} loading={loading}>
            Run
          </Button>
        </Space.Compact>
        <div style={{ marginTop: 16 }}>
          <Text>Last task_id: </Text>
          <Tag color="blue">{taskId || "(none)"}</Tag>
        </div>
      </Card>
      <Alert
        type="info"
        showIcon
        message="샘플 실행 화면입니다"
        description="실제 파일 업로드/모델 폼은 기존 wireframe 기준으로 다음 단계에서 확장합니다."
      />
    </Space>
  );
}

function TaskResultView({ token }: { token: string }) {
  const [taskId, setTaskId] = useState("");
  const [taskData, setTaskData] = useState<TaskData | null>(null);
  const [causal, setCausal] = useState<Record<string, unknown> | null>(null);
  const [recommendation, setRecommendation] = useState<Record<string, unknown> | null>(null);

  const fetchResult = async () => {
    if (!taskId) return;
    try {
      const env = await getEnvelope<TaskData>(`/tasks/${taskId}`, token || undefined);
      if (env.error) throw new Error(env.error.message);
      setTaskData(env.data);
    } catch (err) {
      message.error(String(err));
    }
  };

  const fetchCausal = async () => {
    if (!taskId) return;
    try {
      const env = await getEnvelope<{ causal_report: Record<string, unknown> }>(
        `/tasks/${taskId}/causal-report`,
        token || undefined,
      );
      if (env.error) throw new Error(env.error.message);
      setCausal(env.data?.causal_report ?? null);
    } catch (err) {
      message.error(String(err));
    }
  };

  const fetchAction = async () => {
    if (!taskId) return;
    try {
      const env = await getEnvelope<{ action_recommendation: Record<string, unknown> }>(
        `/tasks/${taskId}/action-recommendation`,
        token || undefined,
      );
      if (env.error) throw new Error(env.error.message);
      setRecommendation(env.data?.action_recommendation ?? null);
    } catch (err) {
      message.error(String(err));
    }
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <Card title="Task Query">
        <Space.Compact style={{ width: 480 }}>
          <Input placeholder="task_id" value={taskId} onChange={(e) => setTaskId(e.target.value)} />
          <Button onClick={fetchResult} icon={<FileSearchOutlined />}>Result</Button>
          <Button onClick={fetchCausal}>Causal</Button>
          <Button onClick={fetchAction}>Action</Button>
        </Space.Compact>
      </Card>

      <Tabs
        items={[
          { key: "result", label: "Task Result", children: <Card><pre>{JSON.stringify(taskData, null, 2)}</pre></Card> },
          { key: "causal", label: "Causal Report", children: <Card><pre>{JSON.stringify(causal, null, 2)}</pre></Card> },
          { key: "action", label: "Recommendation", children: <Card><pre>{JSON.stringify(recommendation, null, 2)}</pre></Card> },
        ]}
      />
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
      <Row gutter={16}>
        <Col span={8}><Card><Statistic title="Plan" value={quota?.plan_tier ?? "-"} /></Card></Col>
        <Col span={8}><Card><Statistic title="Active" value={quota?.active_count ?? 0} /></Card></Col>
        <Col span={8}><Card><Statistic title="Remaining" value={quota?.remaining_capacity ?? 0} /></Card></Col>
      </Row>
      <Card title="Audit Events">
        <Table
          size="small"
          rowKey={(row) => String(row.request_id ?? crypto.randomUUID())}
          columns={auditCols}
          dataSource={audit?.events ?? []}
          pagination={{ pageSize: 10 }}
        />
      </Card>
    </Space>
  );
}

function App() {
  const [collapsed, setCollapsed] = useState(false);
  const [token, setToken] = useState("");
  const [nav, setNav] = useState<NavKey>("dashboard");

  const menuItems = [
    { key: "dashboard", icon: <DashboardOutlined />, label: "Dashboard" },
    { key: "run", icon: <PlayCircleOutlined />, label: "Detection Run" },
    { key: "result", icon: <FileSearchOutlined />, label: "Task Result" },
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
        <Layout>
          <Header style={{ background: "#fff", padding: "0 16px" }}>
            <Title level={4} style={{ margin: "14px 0" }}>React + TypeScript + Ant Design Dashboard</Title>
          </Header>
          <Content style={{ margin: 16 }}>
            <Space direction="vertical" style={{ width: "100%" }} size="large">
              <AuthPanel token={token} setToken={setToken} />
              {nav === "dashboard" && <DashboardView token={token} />}
              {nav === "run" && <DetectionRunView token={token} />}
              {nav === "result" && <TaskResultView token={token} />}
              {nav === "operations" && <OperationsView token={token} />}
            </Space>
          </Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  );
}

export default App;

