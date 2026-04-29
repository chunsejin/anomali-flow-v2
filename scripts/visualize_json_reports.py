"""
Task Result와 Causal Report JSON 시각화 도구

Raw JSON 데이터를 matplotlib, seaborn을 이용해 효과적으로 시각화합니다.
"""

import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Any, Dict, Optional, List, Tuple
from dataclasses import dataclass

# 스타일 설정
sns.set_style("whitegrid")
plt.rcParams["figure.figsize"] = (14, 8)
plt.rcParams["font.size"] = 10


@dataclass
class TaskResultData:
    """Task Result JSON 데이터 구조"""

    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class CausalReportData:
    """Causal Report JSON 데이터 구조"""

    analysis_id: str
    task_id: str
    treatment: str
    outcome: str
    effect_size: float
    confounders: Optional[List[str]] = None
    confidence_interval: Optional[Dict[str, float]] = None
    refutation_result: Optional[str] = None
    dag_version: Optional[str] = None


class JsonVisualizer:
    """JSON 데이터 시각화 클래스"""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = Path(output_dir) if output_dir else Path("./visualizations")
        self.output_dir.mkdir(exist_ok=True)

    def visualize_task_result(self, data: Dict[str, Any], save: bool = True) -> None:
        """Task Result 시각화"""
        print("📊 Task Result 시각화 생성 중...")

        result = data.get("result", {})
        if not isinstance(result, dict):
            print("  ⚠️  Result가 dict 형태가 아닙니다.")
            return

        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(f"Task Result Analysis: {data.get('task_id', 'Unknown')}", fontsize=16, fontweight="bold")

        # 1. Outlier Distribution
        outlier_indices = result.get("outlier_indices", [])
        total_count = len(result.get("index", []))
        outlier_count = len(outlier_indices)
        outlier_rate = (outlier_count / max(1, total_count)) * 100

        ax1 = axes[0, 0]
        sizes = [total_count - outlier_count, outlier_count]
        colors = ["#52c41a", "#ff7875"]
        labels = [f"Normal ({total_count - outlier_count})", f"Outliers ({outlier_count})"]
        ax1.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%", startangle=90)
        ax1.set_title(f"Outlier Distribution\nOutlier Rate: {outlier_rate:.2f}%", fontweight="bold")

        # 2. Outlier Scores Distribution
        ax2 = axes[0, 1]
        outlier_scores = result.get("outlier_scores", [])
        if outlier_scores:
            scores_df = pd.DataFrame({"scores": outlier_scores})
            scores_df["is_outlier"] = scores_df.index.isin(outlier_indices)
            ax2.hist(
                scores_df[~scores_df["is_outlier"]]["scores"],
                bins=30,
                alpha=0.7,
                color="#52c41a",
                label="Normal",
            )
            ax2.hist(
                scores_df[scores_df["is_outlier"]]["scores"],
                bins=30,
                alpha=0.7,
                color="#ff7875",
                label="Outliers",
            )
            ax2.set_xlabel("Outlier Score")
            ax2.set_ylabel("Frequency")
            ax2.set_title("Score Distribution", fontweight="bold")
            ax2.legend()
        else:
            ax2.text(0.5, 0.5, "No outlier scores available", ha="center", va="center")
            ax2.set_title("Score Distribution", fontweight="bold")

        # 3. Numeric Metrics Overview
        ax3 = axes[1, 0]
        metrics = self._extract_numeric_metrics(result)
        if metrics:
            metrics_df = pd.DataFrame(list(metrics.items()), columns=["Metric", "Value"])
            metrics_df = metrics_df.head(10)  # 상위 10개만
            colors_map = ["#1677ff" if v >= 0 else "#ff7875" for v in metrics_df["Value"]]
            ax3.barh(metrics_df["Metric"], metrics_df["Value"], color=colors_map)
            ax3.set_xlabel("Value")
            ax3.set_title("Top Numeric Metrics", fontweight="bold")
            ax3.axvline(x=0, color="black", linestyle="-", linewidth=0.5)
        else:
            ax3.text(0.5, 0.5, "No numeric metrics", ha="center", va="center")
            ax3.set_title("Top Numeric Metrics", fontweight="bold")

        # 4. Status & Metadata
        ax4 = axes[1, 1]
        ax4.axis("off")
        metadata_text = f"""
        Task ID: {data.get('task_id', 'N/A')}
        Status: {data.get('status', 'N/A')}
        
        Summary:
        • Total Records: {total_count}
        • Outliers Detected: {outlier_count}
        • Outlier Rate: {outlier_rate:.2f}%
        
        Created: {data.get('created_at', 'N/A')}
        Updated: {data.get('updated_at', 'N/A')}
        """
        ax4.text(0.1, 0.5, metadata_text, fontsize=11, family="monospace", verticalalignment="center")
        ax4.set_title("Metadata", fontweight="bold")

        plt.tight_layout()
        if save:
            task_id = data.get("task_id", "unknown").replace("/", "_")
            filepath = self.output_dir / f"task_result_{task_id}.png"
            plt.savefig(filepath, dpi=300, bbox_inches="tight")
            print(f"  ✓ 저장됨: {filepath}")
        else:
            plt.show()
        plt.close()

    def visualize_causal_report(self, data: Dict[str, Any], save: bool = True) -> None:
        """Causal Report 시각화"""
        print("📊 Causal Report 시각화 생성 중...")

        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(
            f"Causal Report Analysis: {data.get('analysis_id', 'Unknown')}",
            fontsize=16,
            fontweight="bold",
        )

        # 1. Effect Size & CI
        ax1 = axes[0, 0]
        effect_size = data.get("effect_size", 0)
        ci = data.get("confidence_interval", {})
        ci_low = ci.get("low", 0) if isinstance(ci, dict) else 0
        ci_high = ci.get("high", 1) if isinstance(ci, dict) else 1

        ax1.errorbar(
            [0],
            [effect_size],
            yerr=[[effect_size - ci_low], [ci_high - effect_size]],
            fmt="o",
            markersize=10,
            capsize=10,
            capthick=2,
            color="#1677ff",
            ecolor="#9254de",
        )
        ax1.axhline(y=0, color="black", linestyle="--", linewidth=0.5)
        ax1.set_xlim(-0.5, 0.5)
        ax1.set_ylim(min(0, ci_low - 0.1), max(1, ci_high + 0.1))
        ax1.set_ylabel("Effect Size")
        ax1.set_xticks([])
        ax1.set_title(
            f"Effect Size: {effect_size:.4f}\nCI: [{ci_low:.4f}, {ci_high:.4f}]",
            fontweight="bold",
        )
        ax1.grid(True, alpha=0.3)

        # 2. Causal DAG (간단한 표현)
        ax2 = axes[0, 1]
        ax2.axis("off")

        treatment = data.get("treatment", "Unknown")
        outcome = data.get("outcome", "Unknown")
        confounders = data.get("confounders", []) or []

        dag_text = f"""
        CAUSAL DAG STRUCTURE
        
        Treatment: {treatment}
              ↓
        Outcome: {outcome}
        
        Confounders:
        """
        for conf in confounders:
            dag_text += f"\n  • {conf}"

        ax2.text(0.1, 0.9, dag_text, fontsize=10, family="monospace", verticalalignment="top")
        ax2.set_title("Causal DAG", fontweight="bold")

        # 3. Effect Size Category
        ax3 = axes[1, 0]
        categories = ["Weak\n(<0.1)", "Moderate\n(0.1-0.3)", "Strong\n(0.3-0.5)", "Very Strong\n(>0.5)"]
        thresholds = [0.1, 0.3, 0.5, 1.0]
        colors = ["#d9d9d9", "#d9d9d9", "#d9d9d9", "#d9d9d9"]

        for i, (cat, thresh) in enumerate(zip(categories, thresholds)):
            if effect_size <= thresh:
                colors[i] = "#ff7875"
                break

        bars = ax3.barh(categories, [0.1, 0.2, 0.2, 0.5], left=[0, 0.1, 0.3, 0.5], color=colors)
        ax3.axvline(x=effect_size, color="#1677ff", linewidth=3, label=f"Effect Size: {effect_size:.4f}")
        ax3.set_xlim(0, 1)
        ax3.set_xlabel("Effect Size")
        ax3.set_title("Effect Size Category", fontweight="bold")
        ax3.legend()

        # 4. Refutation & Summary
        ax4 = axes[1, 1]
        ax4.axis("off")

        refutation = data.get("refutation_result", "pending")
        refutation_color = "green" if refutation == "passed" else "orange"

        summary_text = f"""
        CAUSAL ANALYSIS SUMMARY
        
        Analysis ID: {data.get('analysis_id', 'N/A')}
        Task ID: {data.get('task_id', 'N/A')}
        DAG Version: {data.get('dag_version', 'N/A')}
        
        Treatment: {treatment}
        Outcome: {outcome}
        
        Effect Size: {effect_size:.6f}
        Confidence Interval: [{ci_low:.6f}, {ci_high:.6f}]
        CI Width: {ci_high - ci_low:.6f}
        
        Robustness Check: {refutation}
        
        Confounders: {len(confounders)} identified
        {', '.join(confounders[:3]) if confounders else 'None'}
        """
        ax4.text(0.05, 0.95, summary_text, fontsize=10, family="monospace", verticalalignment="top")
        ax4.set_title("Summary", fontweight="bold")

        plt.tight_layout()
        if save:
            analysis_id = data.get("analysis_id", "unknown").replace("/", "_")
            filepath = self.output_dir / f"causal_report_{analysis_id}.png"
            plt.savefig(filepath, dpi=300, bbox_inches="tight")
            print(f"  ✓ 저장됨: {filepath}")
        else:
            plt.show()
        plt.close()

    def visualize_comparison(
        self, task_data: Dict[str, Any], causal_data: Dict[str, Any], save: bool = True
    ) -> None:
        """Task Result와 Causal Report 비교 시각화"""
        print("📊 비교 분석 시각화 생성 중...")

        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle("Task Result vs Causal Report Comparison", fontsize=16, fontweight="bold")

        # 1. Anomaly Rate vs Effect Size
        ax1 = axes[0, 0]
        result = task_data.get("result", {})
        outlier_count = len(result.get("outlier_indices", []))
        total_count = len(result.get("index", []))
        anomaly_rate = (outlier_count / max(1, total_count)) * 100
        effect_size = causal_data.get("effect_size", 0)

        x_pos = [0, 1]
        values = [anomaly_rate, effect_size * 100]  # Effect size를 퍼센트로
        labels = [f"Anomaly Rate\n{anomaly_rate:.2f}%", f"Effect Size\n{effect_size*100:.2f}%"]
        colors = ["#ff7875", "#1677ff"]

        bars = ax1.bar(x_pos, values, color=colors)
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(labels)
        ax1.set_ylabel("Percentage (%)")
        ax1.set_title("Anomaly Rate vs Causal Effect", fontweight="bold")
        ax1.grid(True, alpha=0.3, axis="y")

        # 값 표시
        for i, (bar, val) in enumerate(zip(bars, values)):
            ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2, f"{val:.2f}%", ha="center")

        # 2. Treatment-Outcome Relationship
        ax2 = axes[0, 1]
        ax2.axis("off")
        treatment = causal_data.get("treatment", "Unknown")
        outcome = causal_data.get("outcome", "Unknown")
        confounders = causal_data.get("confounders", []) or []

        relationship_text = f"""
        CAUSAL RELATIONSHIP
        
        Treatment: {treatment}
               ↓ (Effect: {effect_size:.4f})
        Outcome: {outcome}
        
        Confounders:
        {chr(10).join(f'  • {c}' for c in confounders)}
        
        Anomaly Count: {outlier_count}
        Total Records: {total_count}
        
        Interpretation:
        • Anomalies detected: {outlier_count} out of {total_count}
        • Treatment effect: {effect_size:.4f}
        • Confidence: {'High' if causal_data.get('refutation_result') == 'passed' else 'Medium'}
        """

        ax2.text(0.05, 0.95, relationship_text, fontsize=10, family="monospace", verticalalignment="top")
        ax2.set_title("Causal Relationship", fontweight="bold")

        # 3. Confidence Analysis
        ax3 = axes[1, 0]
        ci = causal_data.get("confidence_interval", {})
        ci_low = ci.get("low", 0) if isinstance(ci, dict) else 0
        ci_high = ci.get("high", 1) if isinstance(ci, dict) else 1

        categories = ["CI Low", "Effect Size", "CI High"]
        values = [ci_low, effect_size, ci_high]
        colors = ["#faad14", "#1677ff", "#faad14"]

        ax3.plot(categories, values, "o-", linewidth=2, markersize=10, color="#1677ff")
        for i, (cat, val) in enumerate(zip(categories, values)):
            ax3.text(i, val + 0.02, f"{val:.4f}", ha="center", fontsize=9)

        ax3.fill_between([0, 1], ci_low, ci_high, alpha=0.2, color="#faad14")
        ax3.set_ylabel("Effect Value")
        ax3.set_title("Confidence Interval", fontweight="bold")
        ax3.grid(True, alpha=0.3)

        # 4. Summary
        ax4 = axes[1, 1]
        ax4.axis("off")

        summary_text = f"""
        ANALYSIS SUMMARY
        
        Task ID: {task_data.get('task_id', 'N/A')}
        Analysis ID: {causal_data.get('analysis_id', 'N/A')}
        
        ANOMALIES:
        • Detected: {outlier_count}
        • Total: {total_count}
        • Rate: {anomaly_rate:.2f}%
        
        CAUSAL ANALYSIS:
        • Effect Size: {effect_size:.4f}
        • CI Range: [{ci_low:.4f}, {ci_high:.4f}]
        • Refutation: {causal_data.get('refutation_result', 'N/A')}
        
        KEY INSIGHT:
        {'✓ Anomalies correlate with causal effect' if anomaly_rate > 5 and effect_size > 0.3 else '⚠ Low correlation between anomalies and effect'}
        """

        ax4.text(0.05, 0.95, summary_text, fontsize=10, family="monospace", verticalalignment="top")
        ax4.set_title("Summary", fontweight="bold")

        plt.tight_layout()
        if save:
            task_id = task_data.get("task_id", "unknown").replace("/", "_")
            filepath = self.output_dir / f"comparison_{task_id}.png"
            plt.savefig(filepath, dpi=300, bbox_inches="tight")
            print(f"  ✓ 저장됨: {filepath}")
        else:
            plt.show()
        plt.close()

    @staticmethod
    def _extract_numeric_metrics(obj: Any, prefix: str = "", depth: int = 0, max_depth: int = 2) -> Dict[str, float]:
        """JSON에서 수치 메트릭 추출"""
        if depth > max_depth:
            return {}

        metrics = {}

        if isinstance(obj, (int, float)) and not isinstance(obj, bool):
            return {prefix or "value": float(obj)}

        if isinstance(obj, (list, tuple)):
            numeric_values = [v for v in obj if isinstance(v, (int, float)) and not isinstance(v, bool)]
            if numeric_values:
                avg = np.mean(numeric_values)
                return {prefix or "array_mean": avg}
            return {}

        if isinstance(obj, dict):
            for k, v in obj.items():
                next_prefix = f"{prefix}.{k}" if prefix else k
                metrics.update(JsonVisualizer._extract_numeric_metrics(v, next_prefix, depth + 1, max_depth))

        return metrics


def main():
    """메인 함수"""
    print("🚀 Task Result & Causal Report 시각화 도구\n")

    visualizer = JsonVisualizer(output_dir=Path("./data/visualizations"))

    # 샘플 데이터 생성
    sample_task_result = {
        "task_id": "sample-task-001",
        "status": "SUCCESS",
        "result": {
            "index": list(range(1000)),
            "outlier_indices": list(range(50, 65)) + list(range(200, 210)),
            "outlier_scores": np.random.uniform(0, 1, 1000).tolist(),
        },
        "created_at": "2026-04-28T10:00:00Z",
        "updated_at": "2026-04-28T10:15:00Z",
    }

    sample_causal_report = {
        "analysis_id": "analysis-001",
        "task_id": "sample-task-001",
        "dag_version": "v1",
        "treatment": "algorithm_tuning",
        "outcome": "anomaly_rate",
        "effect_size": 0.35,
        "confidence_interval": {"low": 0.28, "high": 0.42},
        "refutation_result": "passed",
        "confounders": ["seasonality", "data_drift", "model_age"],
    }

    # 시각화 생성
    print("\n📊 시각화 생성 중...\n")
    visualizer.visualize_task_result(sample_task_result, save=True)
    visualizer.visualize_causal_report(sample_causal_report, save=True)
    visualizer.visualize_comparison(sample_task_result, sample_causal_report, save=True)

    print("\n✅ 모든 시각화가 완료되었습니다!")
    print(f"   저장 위치: {visualizer.output_dir}")


if __name__ == "__main__":
    main()
