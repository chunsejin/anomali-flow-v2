import React, { useEffect, useState } from "react";
import { Card, Row, Col, Statistic, Table, Empty, Spin, Button, Space, message } from "antd";
import { BarChartOutlined, ReloadOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { getTaskExplanations, requestTaskExplanation, type ShapExplanation } from "./api";

interface ExplanationViewerProps {
  taskId: string;
  token?: string;
  onLoadingChange?: (loading: boolean) => void;
}

interface FeatureImportanceRow {
  key: string;
  feature: string;
  importance: number;
  percentage: string;
}

interface OutlierExplanationRow {
  key: string;
  instance_id: string;
  top_features: string;
}

export const ExplanationViewer: React.FC<ExplanationViewerProps> = ({
  taskId,
  token,
  onLoadingChange,
}) => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<ShapExplanation | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadExplanations = async () => {
    setLoading(true);
    onLoadingChange?.(true);
    setError(null);

    try {
      const envelope = await getTaskExplanations(taskId, token);

      if (envelope.error) {
        setError(envelope.error.message || "Failed to load explanations");
        return;
      }

      if (envelope.data) {
        setData(envelope.data);
      } else if (envelope.error?.code === "NOT_FOUND") {
        // Try to request new explanations
        const reqEnvelope = await requestTaskExplanation(taskId, token);
        if (!reqEnvelope.error) {
          message.info("Explanation request submitted. Please wait and try again shortly.");
        } else {
          setError(reqEnvelope.error.message || "Could not request explanations");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
      onLoadingChange?.(false);
    }
  };

  useEffect(() => {
    loadExplanations();
  }, [taskId, token]);

  if (loading) {
    return (
      <Card
        title={<span><BarChartOutlined /> Feature Importance & SHAP Analysis</span>}
        extra={<Button icon={<ReloadOutlined />} loading={loading} />}
      >
        <Spin tip="Loading explanations..." />
      </Card>
    );
  }

  if (error) {
    return (
      <Card
        title={<span><BarChartOutlined /> Feature Importance & SHAP Analysis</span>}
        extra={
          <Button icon={<ReloadOutlined />} onClick={loadExplanations}>
            Retry
          </Button>
        }
      >
        <Empty description={error} style={{ marginTop: 24 }} />
      </Card>
    );
  }

  if (!data) {
    return (
      <Card
        title={<span><BarChartOutlined /> Feature Importance & SHAP Analysis</span>}
        extra={
          <Button icon={<ReloadOutlined />} onClick={loadExplanations}>
            Load
          </Button>
        }
      >
        <Empty description="No explanations available" style={{ marginTop: 24 }} />
      </Card>
    );
  }

  // Feature importance data
  const featureImportanceData: FeatureImportanceRow[] = Object.entries(
    data.feature_importance || {},
  )
    .slice(0, 15)
    .map(([feature, importance], index) => {
      const maxImportance = Math.max(...Object.values(data.feature_importance || {}));
      const percentage = maxImportance > 0 ? ((importance / maxImportance) * 100).toFixed(1) : "0";
      return {
        key: `${index}`,
        feature,
        importance: parseFloat(importance.toFixed(4)),
        percentage: `${percentage}%`,
      };
    });

  const featureImportanceColumns: ColumnsType<FeatureImportanceRow> = [
    {
      title: "Feature",
      dataIndex: "feature",
      key: "feature",
      width: "50%",
    },
    {
      title: "Importance Score",
      dataIndex: "importance",
      key: "importance",
      sorter: (a, b) => a.importance - b.importance,
      render: (val) => val.toFixed(4),
    },
    {
      title: "Relative Impact",
      dataIndex: "percentage",
      key: "percentage",
    },
  ];

  // Outlier explanations data
  const outlierExplanationData: OutlierExplanationRow[] = Object.entries(
    data.outlier_explanations || {},
  )
    .slice(0, 10)
    .map(([instanceId, features]) => {
      const topFeatures = (features as Array<{ feature: string; shap_value: number }>)
        .slice(0, 3)
        .map(
          (f) =>
            `${f.feature} (${f.shap_value >= 0 ? "+" : ""}${f.shap_value.toFixed(3)})`,
        )
        .join(", ");
      return {
        key: instanceId,
        instance_id: instanceId,
        top_features: topFeatures,
      };
    });

  const outlierExplanationColumns: ColumnsType<OutlierExplanationRow> = [
    {
      title: "Instance ID",
      dataIndex: "instance_id",
      key: "instance_id",
      width: "30%",
    },
    {
      title: "Top Contributing Features",
      dataIndex: "top_features",
      key: "top_features",
    },
  ];

  return (
    <Card
      title={<span><BarChartOutlined /> Feature Importance & SHAP Analysis</span>}
      extra={
        <Button
          icon={<ReloadOutlined />}
          onClick={loadExplanations}
          loading={loading}
        >
          Refresh
        </Button>
      }
    >
      <Space direction="vertical" style={{ width: "100%" }} size="large">
        {/* Summary statistics */}
        <Row gutter={16}>
          <Col xs={24} sm={12} lg={6}>
            <Statistic
              title="Algorithm"
              value={data.algorithm}
              prefix="<"
              suffix=">"
            />
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Statistic
              title="Analysis Method"
              value={data.method.toUpperCase()}
              prefix="["
              suffix="]"
            />
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Statistic
              title="Samples Analyzed"
              value={data.n_samples_analyzed}
            />
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Statistic
              title="Outliers Explained"
              value={data.n_outliers_analyzed}
            />
          </Col>
        </Row>

        {/* Feature importance table */}
        <Card
          type="inner"
          title="Feature Importance Ranking"
          size="small"
        >
          <Table<FeatureImportanceRow>
            columns={featureImportanceColumns}
            dataSource={featureImportanceData}
            pagination={{ pageSize: 10 }}
            size="small"
            locale={{
              emptyText: "No feature importance data available",
            }}
          />
        </Card>

        {/* Outlier explanations table */}
        <Card
          type="inner"
          title="Top Contributing Features per Outlier"
          size="small"
        >
          <Table<OutlierExplanationRow>
            columns={outlierExplanationColumns}
            dataSource={outlierExplanationData}
            pagination={{ pageSize: 10 }}
            size="small"
            locale={{
              emptyText: "No outlier explanations available",
            }}
          />
        </Card>

        {/* Notes */}
        <Card
          type="inner"
          title="How to interpret"
          size="small"
          style={{ backgroundColor: "#f5f5f5" }}
        >
          <ul style={{ marginBottom: 0 }}>
            <li>
              <strong>Feature Importance:</strong> Measures how much each feature contributes to the anomaly detection decision.
            </li>
            <li>
              <strong>Relative Impact:</strong> Percentage of the maximum importance score among all features.
            </li>
            <li>
              <strong>SHAP Value:</strong> Positive values indicate the feature increases anomaly score; negative values decrease it.
            </li>
            <li>
              <strong>Top Contributing Features:</strong> The features that most influenced the model's decision for each outlier instance.
            </li>
          </ul>
        </Card>
      </Space>
    </Card>
  );
};

export default ExplanationViewer;
