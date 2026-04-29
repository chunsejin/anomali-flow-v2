/**
 * JSON 시각화 컴포넌트
 * Raw JSON 데이터를 효과적으로 표시하고 분석하기 위한 차트 및 시각화 모음
 */

import { useMemo } from "react";
import {
  Card,
  Row,
  Col,
  Space,
  Progress,
  Tag,
  Table,
  Empty,
  Statistic,
  Divider,
  Typography,
  Tooltip,
} from "antd";
import {
  CheckCircleOutlined,
  InfoCircleOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

const { Text } = Typography;

function infoTitle(title: string, description: string) {
  return (
    <Space size={6} align="center">
      <span>{title}</span>
      <Tooltip title={description}>
        <InfoCircleOutlined style={{ color: "#8c8c8c" }} />
      </Tooltip>
    </Space>
  );
}

/**
 * Task Result JSON 구조
 */
export interface TaskResultData {
  task_id: string;
  status: string;
  result?: {
    outlier_indices?: number[];
    outlier_scores?: number[];
    index?: unknown[];
    [key: string]: unknown;
  };
  created_at?: string;
  updated_at?: string;
}

/**
 * Causal Report JSON 구조
 */
export interface CausalReportData {
  analysis_id: string;
  task_id: string;
  treatment: string;
  outcome: string;
  confounders?: string[];
  effect_size: number;
  confidence_interval?: {
    low: number;
    high: number;
  };
  refutation_result?: string;
  dag_version?: string;
  [key: string]: unknown;
}

/**
 * 메트릭 추출 인터페이스
 */
interface MetricRow {
  key: string;
  value: unknown;
  type: "number" | "string" | "boolean" | "array" | "object";
  numValue?: number;
}

/**
 * JSON에서 모든 메트릭 추출 (재귀)
 */
function extractAllMetrics(
  obj: unknown,
  prefix = "",
  depth = 0,
  maxDepth = 3
): MetricRow[] {
  if (depth > maxDepth) return [];
  if (obj === null || obj === undefined) return [];

  const rows: MetricRow[] = [];

  if (typeof obj === "number") {
    return [
      {
        key: prefix || "value",
        value: obj,
        type: "number",
        numValue: obj,
      },
    ];
  }

  if (typeof obj === "string") {
    const numVal = parseFloat(obj);
    return [
      {
        key: prefix || "value",
        value: obj,
        type: "string",
        numValue: Number.isFinite(numVal) ? numVal : undefined,
      },
    ];
  }

  if (typeof obj === "boolean") {
    return [
      {
        key: prefix || "value",
        value: obj,
        type: "boolean",
        numValue: obj ? 1 : 0,
      },
    ];
  }

  if (Array.isArray(obj)) {
    const numericValues = obj.filter(
      (v): v is number => typeof v === "number" && Number.isFinite(v)
    );
    if (numericValues.length > 0) {
      const avg = numericValues.reduce((a, b) => a + b, 0) / numericValues.length;
      return [
        {
          key: prefix || "array_mean",
          value: `${numericValues.length} items, avg: ${avg.toFixed(4)}`,
          type: "array",
          numValue: avg,
        },
      ];
    }
    return [];
  }

  if (typeof obj === "object") {
    for (const [k, v] of Object.entries(obj)) {
      const nextKey = prefix ? `${prefix}.${k}` : k;
      rows.push(...extractAllMetrics(v, nextKey, depth + 1, maxDepth));
    }
  }

  return rows;
}

/**
 * Task Result 차트: 이상치 분포
 */
export function TaskResultOutlierChart({
  data,
}: {
  data: TaskResultData | null;
}) {
  if (!data?.result) {
    return (
      <Card title={infoTitle("Outlier Distribution", "전체 레코드 대비 이상치 비율과 개수를 보여줍니다.")} size="small">
        <Empty description="No result data available" />
      </Card>
    );
  }

  const result = data.result;
  const totalCount = Array.isArray(result.index) ? result.index.length : 0;
  const outlierCount = Array.isArray(result.outlier_indices)
    ? result.outlier_indices.length
    : 0;
  const outlierRate = totalCount > 0 ? (outlierCount / totalCount) * 100 : 0;

  return (
    <Card title={infoTitle("Outlier Distribution", "모델이 탐지한 이상치 비율을 진행바로 확인합니다.")} size="small">
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12}>
          <Statistic
            title="Total Records"
            value={totalCount}
            suffix="items"
          />
        </Col>
        <Col xs={24} sm={12}>
          <Statistic
            title="Outliers Detected"
            value={outlierCount}
            suffix="items"
            valueStyle={{ color: outlierCount > 0 ? "#ff7875" : "#52c41a" }}
          />
        </Col>
      </Row>
      <Divider />
      <div>
        <Space direction="vertical" style={{ width: "100%" }}>
          <div>
            <Space style={{ width: "100%", justifyContent: "space-between" }}>
              <Text>Outlier Rate</Text>
              <Text strong>{outlierRate.toFixed(2)}%</Text>
            </Space>
            <Progress
              percent={Math.min(100, outlierRate)}
              strokeColor={outlierRate > 10 ? "#ff7875" : "#1677ff"}
              status={outlierRate > 10 ? "exception" : "normal"}
            />
          </div>
        </Space>
      </div>
    </Card>
  );
}

/**
 * Causal Report 효과 크기 차트
 */
export function CausalEffectChart({ data }: { data: CausalReportData | null }) {
  if (!data) {
    return (
      <Card title={infoTitle("Causal Effect Analysis", "인과 효과 크기와 신뢰구간을 함께 해석합니다.")} size="small">
        <Empty description="No causal data available" />
      </Card>
    );
  }

  const effect = data.effect_size;
  const ci = data.confidence_interval;
  const ciLow = ci?.low ?? 0;
  const ciHigh = ci?.high ?? 0;
  const ciWidth = ciHigh - ciLow;

  // Effect 크기 평가
  const getEffectLabel = (val: number): [string, string] => {
    if (val > 0.5) return ["Very Strong", "success"];
    if (val > 0.3) return ["Strong", "processing"];
    if (val > 0.1) return ["Moderate", "warning"];
    return ["Weak", "default"];
  };

  const [label, color] = getEffectLabel(effect);

  return (
    <Card title={infoTitle("Causal Effect Analysis", "Effect size, CI width, 범주 강도를 시각적으로 제공합니다.")} size="small">
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12}>
          <Statistic
            title="Effect Size"
            value={effect}
            precision={4}
            suffix={<Tag color={color}>{label}</Tag>}
          />
        </Col>
        <Col xs={24} sm={12}>
          <div>
            <Space direction="vertical" style={{ width: "100%" }}>
              <Text type="secondary">95% Confidence Interval</Text>
              <Text strong>
                [{ciLow.toFixed(4)}, {ciHigh.toFixed(4)}]
              </Text>
              <Text type="secondary">
                CI Width: {ciWidth.toFixed(4)}
              </Text>
            </Space>
          </div>
        </Col>
      </Row>

      {/* Confidence Interval 시각화 */}
      <Divider />
      <div style={{ margin: "16px 0" }}>
        <Space direction="vertical" style={{ width: "100%" }}>
          <Text type="secondary">Effect Range Visualization</Text>
          <svg
            width="100%"
            height="60"
            viewBox="0 0 400 60"
            style={{ border: "1px solid #f0f0f0", borderRadius: "4px" }}
          >
            {/* 축 */}
            <line x1="40" y1="30" x2="360" y2="30" stroke="#d9d9d9" strokeWidth="1" />

            {/* 눈금 */}
            {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
              <g key={tick}>
                <line
                  x1={40 + tick * 320}
                  y1="25"
                  x2={40 + tick * 320}
                  y2="35"
                  stroke="#d9d9d9"
                />
                <text
                  x={40 + tick * 320}
                  y="50"
                  textAnchor="middle"
                  fontSize="10"
                  fill="#666"
                >
                  {tick.toFixed(2)}
                </text>
              </g>
            ))}

            {/* CI 범위 */}
            <rect
              x={40 + ciLow * 320}
              y="20"
              width={ciWidth * 320}
              height="20"
              fill="#b5f"
              opacity="0.3"
              stroke="#9254de"
              strokeWidth="2"
            />

            {/* 효과 크기 포인트 */}
            <circle cx={40 + effect * 320} cy="30" r="6" fill="#1677ff" />
            <circle cx={40 + effect * 320} cy="30" r="9" fill="none" stroke="#1677ff" strokeWidth="1" />
          </svg>
        </Space>
      </div>
    </Card>
  );
}

/**
 * Causal DAG (인과 관계) 시각화
 */
export function CausalDagChart({ data }: { data: CausalReportData | null }) {
  if (!data) {
    return (
      <Card title={infoTitle("Causal DAG Structure", "처치-결과-교란변수 관계를 간단한 DAG 형태로 표시합니다.")} size="small">
        <Empty description="No causal data available" />
      </Card>
    );
  }

  const { treatment, outcome, confounders = [] } = data;
  const safeConfounders = confounders.map((c) => String(c));

  const nodes: Node[] = [
    {
      id: "treatment",
      position: { x: 60, y: 120 },
      data: { label: `Treatment\n${treatment}` },
      style: {
        background: "#e6f4ff",
        border: "1px solid #91caff",
        borderRadius: 8,
        padding: 8,
        width: 180,
        textAlign: "center",
      },
    },
    {
      id: "outcome",
      position: { x: 420, y: 120 },
      data: { label: `Outcome\n${outcome}` },
      style: {
        background: "#f6ffed",
        border: "1px solid #b7eb8f",
        borderRadius: 8,
        padding: 8,
        width: 180,
        textAlign: "center",
      },
    },
    ...safeConfounders.map((conf, idx) => ({
      id: `conf-${idx}`,
      position: { x: 240, y: 40 + idx * 90 },
      data: { label: `Confounder\n${conf}` },
      style: {
        background: "#fff7e6",
        border: "1px solid #ffd591",
        borderRadius: 8,
        padding: 8,
        width: 160,
        textAlign: "center" as const,
      },
    })),
  ];

  const edges: Edge[] = [
    {
      id: "treatment-outcome",
      source: "treatment",
      target: "outcome",
      animated: true,
      label: data.effect_size !== undefined ? `effect: ${data.effect_size.toFixed(4)}` : undefined,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: { stroke: "#1677ff", strokeWidth: 2 },
      labelStyle: { fill: "#1677ff", fontWeight: 600 },
    },
    ...safeConfounders.flatMap((_, idx) => [
      {
        id: `conf-${idx}-treatment`,
        source: `conf-${idx}`,
        target: "treatment",
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { stroke: "#fa8c16", strokeDasharray: "4 4" },
      },
      {
        id: `conf-${idx}-outcome`,
        source: `conf-${idx}`,
        target: "outcome",
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { stroke: "#fa8c16", strokeDasharray: "4 4" },
      },
    ]),
  ];

  const dagHeight = Math.max(280, 220 + safeConfounders.length * 65);

  return (
    <Card title={infoTitle("Causal DAG Structure", "Treatment에서 Outcome으로 이어지는 인과 구조를 보여줍니다.")} size="small">
      <Space direction="vertical" style={{ width: "100%" }}>
        <div style={{ width: "100%", height: dagHeight, border: "1px solid #f0f0f0", borderRadius: 8 }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={false}
            zoomOnScroll={false}
            panOnDrag={false}
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={16} color="#f5f5f5" />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>

        {/* Confounders */}
        {safeConfounders.length > 0 && (
          <>
            <Divider style={{ margin: "12px 0" }} />
            <div>
              <Text type="secondary">Confounders (교란변수):</Text>
              <Space wrap style={{ marginTop: "8px" }}>
                {safeConfounders.map((conf, idx) => (
                  <Tag key={idx} color="orange">
                    ⚠️ {conf}
                  </Tag>
                ))}
              </Space>
            </div>
          </>
        )}

        {/* Refutation Result */}
        {data.refutation_result && (
          <>
            <Divider style={{ margin: "12px 0" }} />
            <Space>
              <Text type="secondary">Robustness Check:</Text>
              <Tag
                color={
                  data.refutation_result === "passed" ? "success" : "warning"
                }
              >
                {data.refutation_result === "passed" ? (
                  <CheckCircleOutlined />
                ) : (
                  <InfoCircleOutlined />
                )}{" "}
                {data.refutation_result}
              </Tag>
            </Space>
          </>
        )}
      </Space>
    </Card>
  );
}

/**
 * Raw JSON 메트릭 테이블
 */
export function JsonMetricsTable({ data }: { data: unknown }) {
  const metrics = useMemo(() => {
    const rows = extractAllMetrics(data);
    return rows
      .filter((row) => row.numValue !== undefined)
      .sort(
        (a, b) => Math.abs((b.numValue ?? 0)) - Math.abs((a.numValue ?? 0))
      )
      .slice(0, 30);
  }, [data]);

  if (metrics.length === 0) {
    return (
      <Card title={infoTitle("Metrics Overview", "JSON 내 수치 메트릭을 자동 추출해 중요도 순으로 정렬합니다.")} size="small">
        <Empty description="No numeric metrics found" />
      </Card>
    );
  }

  const columns: ColumnsType<MetricRow> = [
    {
      title: "Metric Name",
      dataIndex: "key",
      key: "key",
      width: "50%",
      render: (text: string) => <Text ellipsis>{text}</Text>,
    },
    {
      title: "Type",
      dataIndex: "type",
      key: "type",
      width: "15%",
      render: (type: string) => {
        const colorMap: Record<string, string> = {
          number: "blue",
          string: "green",
          boolean: "orange",
          array: "purple",
          object: "red",
        };
        return <Tag color={colorMap[type]}>{type}</Tag>;
      },
    },
    {
      title: "Value",
      dataIndex: "value",
      key: "value",
      width: "20%",
      render: (value: unknown) => {
        if (typeof value === "number") {
          return <Text strong>{value.toFixed(4)}</Text>;
        }
        return <Text ellipsis>{String(value)}</Text>;
      },
    },
    {
      title: "Distribution",
      dataIndex: "numValue",
      key: "numValue",
      width: "15%",
      render: (value: number | undefined) => {
        if (value === undefined) return "-";
        const percent = Math.min(100, Math.max(0, (value / 1) * 100));
        return (
          <Progress
            percent={percent}
            showInfo={false}
            size="small"
            strokeColor={value >= 0 ? "#1677ff" : "#ff7875"}
          />
        );
      },
    },
  ];

  return (
    <Card title={infoTitle("Metrics Overview", "상위 수치 메트릭을 표와 분포 바로 빠르게 탐색합니다.")} size="small">
      <Table<MetricRow>
        columns={columns}
        dataSource={metrics}
        rowKey={(row) => row.key}
        size="small"
        pagination={{ pageSize: 10, showQuickJumper: true }}
        scroll={{ x: 600 }}
      />
    </Card>
  );
}

/**
 * JSON 구조 계층 표시
 */
export function JsonHierarchyView({ data, title = "JSON Structure" }: { data: unknown; title?: string }) {
  const buildHierarchy = (obj: unknown, depth = 0): React.ReactNode => {
    if (depth > 3) return <Text type="secondary">...</Text>;

    if (obj === null) return <Tag>null</Tag>;
    if (obj === undefined) return <Tag>undefined</Tag>;
    if (typeof obj === "boolean") return <Tag color={obj ? "success" : "error"}>{String(obj)}</Tag>;
    if (typeof obj === "number") return <Text code>{obj.toFixed(4)}</Text>;
    if (typeof obj === "string") return <Text ellipsis code>{obj}</Text>;

    if (Array.isArray(obj)) {
      if (obj.length === 0) return <Tag>[]</Tag>;
      return (
        <Space direction="vertical" size="small" style={{ marginLeft: "16px" }}>
          <Tag>Array[{obj.length}]</Tag>
          {obj.slice(0, 5).map((item, idx) => (
            <div key={idx}>
              [{idx}]: {buildHierarchy(item, depth + 1)}
            </div>
          ))}
          {obj.length > 5 && <Text type="secondary">... +{obj.length - 5} more</Text>}
        </Space>
      );
    }

    if (typeof obj === "object") {
      const entries = Object.entries(obj);
      return (
        <Space direction="vertical" size="small" style={{ marginLeft: "16px" }}>
          {entries.map(([k, v]) => (
            <div key={k}>
              <Text strong>{k}:</Text> {buildHierarchy(v, depth + 1)}
            </div>
          ))}
        </Space>
      );
    }

    return <Text>{String(obj)}</Text>;
  };

  return (
    <Card title={infoTitle(title, "JSON 구조를 최대 3단계 깊이로 계층적으로 표시합니다.")} size="small">
      <div style={{ maxHeight: "400px", overflowY: "auto", fontSize: "12px" }}>
        {buildHierarchy(data)}
      </div>
    </Card>
  );
}

/**
 * Task Result와 Causal Report 비교 대시보드
 */
export function ComparisonDashboard({
  taskData,
  causalData,
}: {
  taskData: TaskResultData | null;
  causalData: CausalReportData | null;
}) {
  if (!taskData && !causalData) {
    return (
      <Card title={infoTitle("Analysis Comparison Dashboard", "Task Result와 Causal Report를 함께 비교합니다.")}>
        <Empty description="No data available for comparison" />
      </Card>
    );
  }

  const taskOutlierCount = Array.isArray(
    taskData?.result?.outlier_indices
  )
    ? taskData.result.outlier_indices.length
    : 0;
  const effectSize = causalData?.effect_size ?? 0;

  return (
    <Card title={infoTitle("Analysis Comparison Dashboard", "이상치 탐지 결과와 인과 효과를 한눈에 비교합니다.")} size="small">
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} md={6}>
          <Statistic
            title="Anomalies Detected"
            value={taskOutlierCount}
            valueStyle={{ color: taskOutlierCount > 0 ? "#ff7875" : "#52c41a" }}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Statistic
            title="Causal Effect"
            value={effectSize}
            precision={4}
            valueStyle={{
              color: effectSize > 0.3 ? "#ff7875" : "#1677ff",
            }}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Statistic
            title="Treatment"
            value={causalData?.treatment ?? "-"}
            valueStyle={{ fontSize: "14px" }}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Statistic
            title="Outcome"
            value={causalData?.outcome ?? "-"}
            valueStyle={{ fontSize: "14px" }}
          />
        </Col>
      </Row>

      {/* 연관성 분석 */}
      <Divider />
      <Text type="secondary">
        <InfoCircleOutlined /> Insight: {taskOutlierCount > 0 ? `발견된 ${taskOutlierCount}개 이상치가 ${causalData?.outcome ?? "결과"}에 ${(effectSize * 100).toFixed(1)}% 영향을 미칩니다.` : "이상치가 없습니다."}
      </Text>
    </Card>
  );
}
