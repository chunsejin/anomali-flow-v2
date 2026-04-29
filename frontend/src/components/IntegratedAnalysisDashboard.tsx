/**
 * 통합 분석 대시보드
 * Task Result와 Causal Report를 함께 분석하고 비교
 */

import { useState } from "react";
import {
  Card,
  Row,
  Col,
  Space,
  Input,
  Button,
  Empty,
  Spin,
  message,
  Divider,
  Tabs,
  Tag,
  Tooltip,
} from "antd";
import { LoadingOutlined, ExclamationOutlined, InfoCircleOutlined } from "@ant-design/icons";
import {
  TaskResultOutlierChart,
  CausalEffectChart,
  CausalDagChart,
  ComparisonDashboard,
  JsonMetricsTable,
} from "./JsonVisualizer";

interface AnalysisData {
  taskId: string;
  taskResult: Record<string, unknown> | null;
  causalReport: Record<string, unknown> | null;
  loading: boolean;
  error: string | null;
}

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
 * 통합 분석 뷰
 */
export function IntegratedAnalysisDashboard({
  token,
  getEnvelopeFunc,
}: {
  token: string | null;
  getEnvelopeFunc: <T>(url: string, token?: string) => Promise<{ data?: T; error?: { message: string } }>;
}) {
  const [taskId, setTaskId] = useState("");
  const [analysis, setAnalysis] = useState<AnalysisData>({
    taskId: "",
    taskResult: null,
    causalReport: null,
    loading: false,
    error: null,
  });

  const loadAnalysis = async () => {
    if (!taskId.trim()) {
      message.warning("Please enter a task_id");
      return;
    }

    setAnalysis((prev) => ({
      ...prev,
      loading: true,
      error: null,
    }));

    try {
      // Task Result 로드
      const taskEnv = await getEnvelopeFunc<{ result: Record<string, unknown> }>(
        `/tasks/${taskId}`,
        token || undefined
      );

      if (taskEnv.error) {
        throw new Error(`Task Result: ${taskEnv.error.message}`);
      }

      // Causal Report 로드
      const causalEnv = await getEnvelopeFunc<{ causal_report: Record<string, unknown> }>(
        `/tasks/${taskId}/causal-report`,
        token || undefined
      );

      const causalData = causalEnv.data?.causal_report || null;

      setAnalysis({
        taskId,
        taskResult: taskEnv.data?.result || null,
        causalReport: causalData,
        loading: false,
        error: null,
      });

      message.success("Analysis loaded successfully!");
    } catch (err) {
      const errorMsg = String(err);
      setAnalysis((prev) => ({
        ...prev,
        loading: false,
        error: errorMsg,
      }));
      message.error(errorMsg);
    }
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      {/* Input Section */}
      <Card title={infoTitle("Integrated Analysis Dashboard", "Task Result와 Causal Report를 함께 로드해 통합 분석합니다.")} size="small">
        <Space style={{ width: "100%" }}>
          <Input
            placeholder="Enter task_id"
            value={taskId}
            onChange={(e) => setTaskId(e.target.value)}
            style={{ width: "300px" }}
            onPressEnter={loadAnalysis}
          />
          <Button type="primary" onClick={loadAnalysis} loading={analysis.loading}>
            Load Analysis
          </Button>
          {analysis.taskId && (
            <Tag color="blue">
              Current: {analysis.taskId}
            </Tag>
          )}
        </Space>
      </Card>

      {/* Error Display */}
      {analysis.error && (
        <Card
          style={{ borderColor: "#ff7875" }}
          title={
            <Space>
              <ExclamationOutlined style={{ color: "#ff7875" }} />
              Error
            </Space>
          }
        >
          <span style={{ color: "#ff7875" }}>{analysis.error}</span>
        </Card>
      )}

      {/* Loading State */}
      {analysis.loading && (
        <Card style={{ textAlign: "center", padding: "40px" }}>
          <Spin indicator={<LoadingOutlined style={{ fontSize: 48 }} spin />} />
          <p>Loading analysis data...</p>
        </Card>
      )}

      {/* Success State */}
      {!analysis.loading && !analysis.error && analysis.taskId && (
        <Tabs
          defaultActiveKey="comparison"
          items={[
            {
              key: "comparison",
              label: "Comparison Overview",
              children: (
                <Space direction="vertical" style={{ width: "100%" }}>
                  <ComparisonDashboard
                    taskData={analysis.taskResult as any}
                    causalData={analysis.causalReport as any}
                  />

                  <Row gutter={[16, 16]}>
                    <Col xs={24} md={12}>
                      <TaskResultOutlierChart
                        data={analysis.taskResult as any}
                      />
                    </Col>
                    <Col xs={24} md={12}>
                      <CausalEffectChart
                        data={analysis.causalReport as any}
                      />
                    </Col>
                  </Row>

                  <Row gutter={[16, 16]}>
                    <Col xs={24} md={12}>
                      <CausalDagChart
                        data={analysis.causalReport as any}
                      />
                    </Col>
                  </Row>
                </Space>
              ),
            },
            {
              key: "taskResult",
              label: "Task Result Metrics",
              children: (
                <Space direction="vertical" style={{ width: "100%" }}>
                  {analysis.taskResult ? (
                    <JsonMetricsTable data={analysis.taskResult} />
                  ) : (
                    <Empty description="No task result data" />
                  )}
                </Space>
              ),
            },
            {
              key: "causalReport",
              label: "Causal Metrics",
              children: (
                <Space direction="vertical" style={{ width: "100%" }}>
                  {analysis.causalReport ? (
                    <JsonMetricsTable data={analysis.causalReport} />
                  ) : (
                    <Empty description="No causal report data" />
                  )}
                </Space>
              ),
            },
            {
              key: "correlation",
              label: "Correlation Analysis",
              children: (
                <Card size="small" title={infoTitle("Correlation Analysis", "이상치 비율과 인과 효과의 강도/신뢰도를 함께 해석합니다.")}>
                  <CorrelationAnalysis
                    taskResult={analysis.taskResult}
                    causalReport={analysis.causalReport}
                  />
                </Card>
              ),
            },
          ]}
        />
      )}

      {/* Empty State */}
      {!analysis.loading && !analysis.error && !analysis.taskId && (
        <Card style={{ textAlign: "center", padding: "40px" }}>
          <Empty description="Enter a task_id to start analysis" />
        </Card>
      )}
    </Space>
  );
}

/**
 * 상관관계 분석 컴포넌트
 */
function CorrelationAnalysis({
  taskResult,
  causalReport,
}: {
  taskResult: Record<string, unknown> | null;
  causalReport: Record<string, unknown> | null;
}) {
  if (!taskResult || !causalReport) {
    return <Empty description="Missing data for correlation analysis" />;
  }

  // 이상치 개수 추출
  const outlierCount = Array.isArray((taskResult as any)?.outlier_indices)
    ? (taskResult as any).outlier_indices.length
    : 0;

  const totalCount = Array.isArray((taskResult as any)?.index)
    ? (taskResult as any).index.length
    : 1;

  const outlierRate = (outlierCount / Math.max(1, totalCount)) * 100;

  // Effect size 추출
  const effectSize = (causalReport as any)?.effect_size ?? 0;

  // 신뢰도 구간 추출
  const ci = (causalReport as any)?.confidence_interval;
  const ciLow = ci?.low ?? 0;
  const ciHigh = ci?.high ?? 1;
  const ciWidth = ciHigh - ciLow;

  // 상관관계 분석
  const correlation = {
    hasOutliers: outlierCount > 0,
    outlierRate,
    hasStrongEffect: effectSize > 0.3,
    effectSize,
    hasNarrowCI: ciWidth < 0.1,
    ciWidth,
    treatment: (causalReport as any)?.treatment || "unknown",
    outcome: (causalReport as any)?.outcome || "unknown",
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <h3>Anomaly-Causality Correlation</h3>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <Card size="small" title={infoTitle("Anomaly Severity", "이상치 비율과 존재 여부를 통해 이상 탐지 강도를 평가합니다.")}>
            <Space direction="vertical" style={{ width: "100%" }}>
              <div>
                <Tooltip title="Rate of anomalies detected">
                  <Tag
                    color={
                      correlation.outlierRate > 10
                        ? "red"
                        : correlation.outlierRate > 5
                          ? "orange"
                          : "green"
                    }
                  >
                    {correlation.outlierRate.toFixed(2)}% Anomalies
                  </Tag>
                </Tooltip>
              </div>
              <div>
                <Tooltip title="Indicates high variance in outcomes">
                  <Tag color={correlation.hasOutliers ? "red" : "green"}>
                    {correlation.hasOutliers ? "Anomalies Present" : "No Anomalies"}
                  </Tag>
                </Tooltip>
              </div>
            </Space>
          </Card>
        </Col>

        <Col xs={24} md={12}>
          <Card size="small" title={infoTitle("Causal Effect Strength", "effect size와 CI 폭으로 인과 효과의 신뢰도를 판단합니다.")}>
            <Space direction="vertical" style={{ width: "100%" }}>
              <div>
                <Tooltip title="Magnitude of treatment effect">
                  <Tag
                    color={
                      correlation.effectSize > 0.5
                        ? "red"
                        : correlation.effectSize > 0.3
                          ? "orange"
                          : "blue"
                    }
                  >
                    {correlation.effectSize.toFixed(4)} Effect Size
                  </Tag>
                </Tooltip>
              </div>
              <div>
                <Tooltip title="Confidence interval narrowness - lower is better">
                  <Tag color={correlation.hasNarrowCI ? "green" : "orange"}>
                    CI Width: {correlation.ciWidth.toFixed(4)}
                  </Tag>
                </Tooltip>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>

      <Divider />

      <Card size="small" title={infoTitle("Interpretation", "이상치와 인과효과 조합을 기반으로 해석 가이드를 제공합니다.")}>
        <Space direction="vertical" style={{ width: "100%" }}>
          {correlation.hasOutliers && !correlation.hasStrongEffect && (
            <p>
              ⚠️ <strong>High Anomalies, Weak Effect:</strong> Anomalies are detected but the
              identified treatment ({correlation.treatment}) shows weak causal effect on outcome (
              {correlation.outcome}). Consider other confounders or treatments.
            </p>
          )}

          {correlation.hasOutliers && correlation.hasStrongEffect && (
            <p>
              ✓ <strong>High Anomalies, Strong Effect:</strong> Anomalies align with strong causal
              effect. The treatment ({correlation.treatment}) significantly impacts the outcome (
              {correlation.outcome}).
            </p>
          )}

          {!correlation.hasOutliers && correlation.hasStrongEffect && (
            <p>
              ℹ️ <strong>No Anomalies, Strong Effect:</strong> Treatment effect is strong but no
              anomalies were detected. The system is performing normally despite the treatment
              effect.
            </p>
          )}

          {!correlation.hasOutliers && !correlation.hasStrongEffect && (
            <p>
              ✓ <strong>Stable System:</strong> No anomalies detected and treatment effect is weak.
              The system appears stable.
            </p>
          )}

          {correlation.hasNarrowCI && (
            <p>
              ✓ <strong>High Confidence:</strong> Narrow confidence interval ({correlation.ciWidth.toFixed(4)})
              indicates reliable effect estimation.
            </p>
          )}

          {!correlation.hasNarrowCI && (
            <p>
              ⚠️ <strong>Low Confidence:</strong> Wide confidence interval (
              {correlation.ciWidth.toFixed(4)}) suggests uncertainty in effect estimation.
            </p>
          )}
        </Space>
      </Card>
    </Space>
  );
}
