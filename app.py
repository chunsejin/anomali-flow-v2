import numpy as np
import streamlit as st
import requests
import pandas as pd
import time
import json
import uuid
import tensorly as tl
from sklearn.preprocessing import StandardScaler
from tensorly.decomposition import parafac
from sklearn.preprocessing import MinMaxScaler,LabelEncoder
from sklearn.mixture import GaussianMixture
from bokeh.plotting import figure
from bokeh.palettes import Blues256
from bokeh.models import LinearColorMapper,Spacer,Range1d, ColorBar, ColumnDataSource, Legend, HoverTool, TableColumn, DataTable, CustomJS, TapTool
from bokeh.transform import transform, jitter
from bokeh.layouts import column, row
from prefect import flow, task
from auth import build_request_context, decode_token, get_auth_settings
from streamlit_api import (
    fetch_action_recommendation,
    fetch_audit_events,
    fetch_causal_report,
    fetch_dashboard_summary,
    fetch_quota_status,
    submit_task,
    fetch_task_result,
    wait_for_task_result,
)

# ?ê°???ì¤??
#@task
#def create_visualizations(result, graph_type, x_column, y_column, df, selected_features):
def create_visualizations(result, graph_type, x_column, y_column, df, start_handle=None, end_handle=None):
    
    # outlier_indices ë³?ê? ?¬ì©?ê¸° ?ì ë¹?ë¦¬ì¤?¸ë¡ ì´ê¸°??
    outlier_indices = []
    
    outlier_indices = result.get('outlier_indices')
    outlier_probabilities = result.get('outlier_probabilities')
    root_cause_scores = result.get('root_cause_scores')
    index = result.get('index')
    
    # Root Cause Score ?í¸ë§??ì±
    if root_cause_scores:
        # ?ê°?ë? ?í ?°ì´??ì¤ë¹?
        timestamps = list(dict.fromkeys([str(ts) for ts in index if str(ts) in root_cause_scores]))
        features = list(next(iter(root_cause_scores.values())).keys())
        # ?í¸ë§??°ì´???ì±
        heatmap_data = {
            'timestamp': [],
            'feature': [],
            'score': []
        }
    
        for timestamp in timestamps:
            for feature in features:
                score = root_cause_scores.get(str(timestamp), {}).get(feature, 0)
                heatmap_data['timestamp'].append(timestamp)
                heatmap_data['feature'].append(feature)
                heatmap_data['score'].append(score)
    
        # ?ê·??
        scaler = MinMaxScaler(feature_range=(0, 100))
        normalized_scores = scaler.fit_transform(np.array(heatmap_data['score']).reshape(-1, 1)).flatten()
        heatmap_data['score'] = normalized_scores
    
        source = ColumnDataSource(data=heatmap_data)
    
        # ?ì ë§¤í¼ ?ì±
        mapper = LinearColorMapper(palette="Blues256", low=100, high=0)
        
        # ?í¸ë§??ë¡¯ ?ì±
        p_heatmap = figure(
            title="Root Cause Scores Heatmap",
            x_range=timestamps,
            y_range=features,
            x_axis_label='Timestamp',
            y_axis_label='Feature',
            plot_width=1000,
            plot_height=400,
            tools="pan,wheel_zoom,box_zoom,reset",
            tooltips=[('Feature', '@feature'), ('Timestamp', '@timestamp'), ('Score', '@score')],
        )
    
        p_heatmap.rect(
            x="timestamp",
            y="feature",
            width=1,
            height=1,
            source=source,
            fill_color=transform('score', mapper),
            line_color=None
        )
    
        # ?ì ë°?ì¶ê?
        color_bar = ColorBar(color_mapper=mapper, location=(0, 0))
        p_heatmap.add_layout(color_bar, 'right')
    
        # ?í¸ë§µì Streamlit???ì
        st.bokeh_chart(p_heatmap)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<hr>", unsafe_allow_html=True)

        
        st.markdown(
            "<p style='color:grey; font-size:12px; line-height:0.8;'>| outlierë¡??ë³?ë ê·¼ë³¸?ì¸ ?ì¸??ë¶ì?ê³ , ê°??ì??ê¸°ì¬?ë? ?ìë¡??ê°?í ê·¸ë?ì?ë¤. </p>",
            unsafe_allow_html=True
        )
        
        # ?¬ë°± ì¶ê?
        st.markdown("<br><br><br><br><br>", unsafe_allow_html=True)

    # ì¶ê? ê·¸ë??
    outlier_indices_all = [i for i in outlier_indices if pd.notna(i) and i in df.index]
    inlier_indices_all = [i for i in df.index if i not in outlier_indices_all]
    
    inliers_all = df.loc[inlier_indices_all] if inlier_indices_all is not None else pd.DataFrame()
    outliers_all = df.loc[outlier_indices_all] if outlier_indices_all is not None else pd.DataFrame()
    
    # ?ì²´ Data??ColumnDataSource ?ì±
    source_inliers_all = ColumnDataSource(data=dict(
        x=inlier_indices_all,
        y=inliers_all[y_column] if not inliers_all.empty else [],
    ))    
    
    source_outliers_all = ColumnDataSource(data=dict(
        x=outlier_indices_all if outlier_indices_all is not None else [],  # outlier ?¸ë±???¬ì©
        y=outliers_all[y_column] if not outliers_all.empty else [],  # outlier ê°?
    ))
    
    p_all = figure(title="Anomaly Score Graph", x_axis_label="Index", y_axis_label="Value", 
               plot_width=1000, plot_height=400,
               tools="pan,wheel_zoom,box_zoom,reset", 
               tooltips=[("Index", "@x"), ("Value", "@y")])
    
    # yì¶?ë²ì ê³ì° ë°??ì¥
    y_min, y_max = min(inliers_all[y_column].min(), outliers_all[y_column].min()), max(inliers_all[y_column].max(), outliers_all[y_column].max())
    y_extension = 2  # ì¶ê??ê³  ?¶ì? ë²ì
    p_all.y_range = Range1d(y_min - y_extension, y_max + y_extension)
    
    p_all.title.align = "center"
    p_all.title.offset = 10
    p_all.title.text_font_style = "bold"
    p_all.title.text_font_size = "13pt"
    
    p_all.xaxis.axis_label_text_font_style = "italic"
    p_all.xaxis.axis_label_text_font_size = "10pt"
    
    p_all.yaxis.axis_label_text_font_style = "italic"
    p_all.yaxis.axis_label_text_font_size = "10pt"

    # ?ì²´ ?°ì´?°ì ê·¸ë?ì inliers? outliers ê·¸ë¦¬ê¸?
    p_all.line(x='x', y='y', source=source_inliers_all, line_color='#3A7CA5', line_width=2, legend_label='Inliers')
    p_all.circle(x='x', y='y', source=source_outliers_all, color='#FF6B6B', size=6, legend_label='Outliers')
    
    # Anomaly Score Graph ì¶ë ¥
    st.bokeh_chart(p_all)
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    
    # ê·¸ë???ì ?¤ëª ì¶ê?
    st.markdown(
        "<p style='color:grey; font-size:12px; line-height:0.8;'>| ?ì²´ ?°ì´?°ì?ì outlier? inlier??ë¶í¬ë¥??í??´ë ê·¸ë?ì?ë¤.</p>",
        unsafe_allow_html=True
    )
    
    # ?¬ë°± ì¶ê?
    st.markdown("<br><br><br><br><br>", unsafe_allow_html=True)
    
    
    # ?ë ¥ êµ¬ê°(start_handle, end_handle)???´ë¹?ë ?°ì´?°ë§ ? í
    if start_handle is None or end_handle is None:
        filtered_df = df  # ?ì²´ ?°ì´???¬ì©
    else:
        # ?ì¹ ê¸°ë°?¼ë¡ ?ë ¥??ë²ì???´ë¹?ë ?°ì´?°ë? ?í°ë§?
        filtered_df = df.iloc[df.index.get_loc(start_handle):df.index.get_loc(end_handle) + 1]


    # ?´ìì¹ì? ?ì ?°ì´??êµ¬ë¶
    if outlier_indices is not None and len(outlier_indices) > 0:
        inliers = filtered_df.drop(outlier_indices)
        outliers = filtered_df.loc[outlier_indices]
    else:
        inliers = filtered_df
        outliers = pd.DataFrame()  # ë¹?DataFrame?¼ë¡ ì²ë¦¬


    # Inliers? Outliers?????ê°ê°??ColumnDataSource ?ì±
    source_inliers = ColumnDataSource(data=dict(
        x=inliers[x_column], 
        y=inliers[y_column],
        **{feature: inliers[feature] for feature in inliers.columns if feature not in [x_column, y_column]}
    ))

    if not outliers.empty:
        outliers_data = {'x': outliers[x_column], 'y': outliers[y_column]}
        for col in outliers.columns:
            if col != x_column and col != y_column:
                outliers_data[col] = outliers[col]
        source_outliers = ColumnDataSource(data=outliers_data)
    else:
        source_outliers = None

    # Graph2 ?¤ì 
    p_2d = figure(title=f"{x_column} vs {y_column}", 
                tools="pan,wheel_zoom,box_zoom,reset", 
                tooltips=[("X", "@x"), ("Y", "@y")])
    
    p_2d.title.align = "left"
    p_2d.title.offset = 10
    p_2d.title.text_font_style = "bold"
    p_2d.title.text_font_size = "13pt"
    
    p_2d.xaxis.axis_label_text_font_style = "italic"
    p_2d.xaxis.axis_label_text_font_size = "10pt"
    
    p_2d.yaxis.axis_label_text_font_style = "italic"
    p_2d.yaxis.axis_label_text_font_size = "10pt"

    # ê·¸ë????ì ?°ë¥¸ ê·¸ë¦¬ê¸?
    if graph_type == "Line Graph":
        p_2d.line(x='x', y='y', source=source_inliers, line_color='#3A7CA5', line_width=2, legend_label='Inliers')
        if source_outliers is not None:
            p_2d.circle(x='x', y='y', source=source_outliers, color='#FF6B6B', size=6, legend_label='Outliers')

    elif graph_type == "Scatter Plot":
        p_2d.circle(x='x', y='y', source=source_inliers, color='#3A7CA5', size=6, legend_label='Inliers')
        if source_outliers is not None:
            p_2d.circle(x='x', y='y', source=source_outliers, color='#FF6B6B', size=6, legend_label='Outliers')

    elif graph_type == "Bar Graph":
        p_2d.vbar(x='x', top='y', source=source_inliers, width=0.9, color='#3A7CA5', alpha=0.8, legend_label='Inliers')
        if source_outliers is not None:
            p_2d.circle(x='x', y='y', source=source_outliers, color='#FF6B6B', size=6, legend_label='Outliers')
        p_2d.xgrid.grid_line_color = None
        p_2d.y_range.start = 0

    if graph_type == "Scatter Plot (Jittered)":
        # Inliers ?°ì´?°ë¡ Scatter Plot (Jittering) ?ì±
        p_2d.circle(x=jitter('x', width=0.1), y='y', source=source_inliers, color='#3A7CA5', size=6, legend_label='Inliers')
        # Outliers ?°ì´?°ê? ì¡´ì¬?ë©´ Outliers???ì
        if source_outliers is not None:
            p_2d.circle(x=jitter('x', width=0.1), y='y', source=source_outliers, color='#FF6B6B', size=6, legend_label='Outliers')
            
        # xì¶??ì´ë¸ì ?ë ê°??¬ì© (LabelEncoder ?¬ì©)
        if x_column in label_encoders:
            x_ticks = sorted(set(inliers[x_column]))
            x_labels = label_encoders[x_column].inverse_transform(x_ticks)
            
            x_labels = pd.Series(x_labels).fillna('Unknown').tolist()
            
            p_2d.xaxis.ticker = x_ticks
            p_2d.xaxis.major_label_overrides = {tick: label for tick, label in zip(x_ticks, x_labels)}

        # yì¶??ì´ë¸ì ?ë ê°??¬ì© (LabelEncoder ?¬ì©)
        if y_column in label_encoders:
            y_ticks = sorted(set(inliers[y_column]))
            y_labels = label_encoders[y_column].inverse_transform(y_ticks)
            p_2d.yaxis.ticker = y_ticks
            p_2d.yaxis.major_label_overrides = {tick: label for tick, label in zip(y_ticks, y_labels)}

        # xì¶?ë°?yì¶??ì´ë¸??¤ì 
        p_2d.xaxis.axis_label = x_column
        p_2d.yaxis.axis_label = y_column

    # Hover tool ì¶ê?
    hover_tool_3 = HoverTool(tooltips=[('x', '@x'), ('y', '@y')], mode='vline')
    p_2d.add_tools(hover_tool_3)

    # ?ì´ë¸ì ì¶ë ¥???°ì´?°ë? ??¥í  ColumnDataSource ?ì± (ë¹??°ì´?°ë¡ ì´ê¸°??
    selected_point_features = ColumnDataSource(data=dict(Feature=[], Value=[]))

    # ?ì´ë¸?ì»¬ë¼ ?¤ì 
    columns = [
        TableColumn(field="Feature", title="Feature"),
        TableColumn(field="Value", title="Value"),
    ]

    # DataTable ?ì±
    data_table = DataTable(source=selected_point_features, columns=columns, width=400, height=280)

    # TapTool ì¶ê? ë°?ì½ë°± ?°ê²°
    tap_callback = CustomJS(args=dict(source_outliers=source_outliers, source_inliers=source_inliers, selected_source=selected_point_features), code="""
    console.log("Callback triggered");

    var outlier_selected_indices = source_outliers.selected.indices;
    var inlier_selected_indices = source_inliers.selected.indices;

    var data, selected_indices;

    if (outlier_selected_indices.length > 0) {
        selected_indices = outlier_selected_indices;
        data = source_outliers.data;
        source_inliers.selected.indices = [];
    } else if (inlier_selected_indices.length > 0) {
        selected_indices = inlier_selected_indices;
        data = source_inliers.data;
        source_outliers.selected.indices = [];
    }

    if (selected_indices.length > 0) {
        var index = selected_indices[0];
        var feature_names = Object.keys(data).filter(name => name !== 'x' && name !== 'y');
        var feature_values = feature_names.map(name => data[name][index]);

        var table_data = { Feature: [], Value: [] };
        for (var i = 0; i < feature_names.length; i++) {
            table_data['Feature'].push(feature_names[i]);
            table_data['Value'].push(feature_values[i]);
        }

        selected_source.data = table_data;
        selected_source.change.emit();
        console.log("Table updated");
    }
    """)

    if source_outliers is not None and source_inliers is not None:
        tap_tool = TapTool()
        p_2d.add_tools(tap_tool)
        source_outliers.selected.js_on_change('indices', tap_callback)
        source_inliers.selected.js_on_change('indices', tap_callback)
    
    # ê·¸ë?ì? ?¤ëª ?¬ì´???¬ë°± ì¶ê? (?ì ??
    st.markdown("<br>", unsafe_allow_html=True) 
    

        
    layout = row(p_2d, data_table)
    st.bokeh_chart(layout)  
    st.markdown("<hr>", unsafe_allow_html=True)
    
    # ??ë²ì§¸ ê·¸ë?ì? ?°ì´???ì´ë¸?
    st.markdown(
        "<p style='color:grey;font-size:12px; line-height:0.8;'>| ?ì ? í????ê°ì featureë¥?ê¸°ì??¼ë¡ outlier? inlier??ë¶í¬ë¥??ê°?í ê·¸ë?ì?ë¤. </p>"
        "<p style='color:grey; font-size:12px; line-height:0.8;'>  ???ì¸???ì¸?ê³  ?¶ì? pointë¥??´ë¦­?´ë³´?¸ì. ?¤ë¥¸ìª?table?ì ? í??point??????¸ë??¬í­???ì¸?????ìµ?ë¤.</p>",
        unsafe_allow_html=True
    )
    
    st.markdown("<br><br><br><br><br>", unsafe_allow_html=True)

    


######## Time Series ?°ì´??Prefect?í¬?ë¡??and tasks ########
# ?°ì´??ë¡ë ë°?? í ê°ì?
def classify_dataset(df):
    num_cols = len(df.columns)
    
    # Time series: ?ê° ê´???´ì´ ì¡´ì¬?ëì§ ?ì¸
    time_series_cols = [col for col in df.columns if pd.api.types.is_datetime64_any_dtype(df[col]) or 
                        (df[col].dtype == 'object' and pd.to_datetime(df[col], errors='coerce').notna().any())]

    if time_series_cols:
        return 'time_series'

    # Categorical: ?´ì ê³ ì ??ê°ì´ ?¼ì  ?ê³ì¹?ë¯¸ë§?´ë©´ categoricalë¡?ë¶ë¥
    categorical_count = sum(
        (df[col].dtype == 'object' or df[col].nunique() / len(df) < 0.05)
        for col in df.columns
    )
    if categorical_count / num_cols > 0.5:
        return 'categorical'

    # Numerical: ?ë¶ë¶ì ?´ì´ ?«ì?ì¸ ê²½ì°
    numerical_count = sum(np.issubdtype(df[col].dtype, np.number) for col in df.columns)
    if numerical_count / num_cols > 0.5:
        return 'numerical' # 'numerical'
    
    return 'unknown'

# ?°ì´???ì²ë¦?
def timeseries_preprocess(df, tensor_rank, sliding_window_size):
    # 0ë²ì§¸ ?´ì ?°ë¡ ???(?ë³¸ ?°ì´??ê·¸ë?ë¡??¬ì©)
    first_col = df.iloc[:, 0]

    # ?ë¨¸ì§ ?´ë§ ?ì²ë¦?ì§í
    df_processed = df.iloc[:, 1:].copy()
    
    for col in df_processed.columns:
        # ?«ì ë³?ì´ ?ì??ê²½ì°ë¥??ë¹í´ ëª¨ë  ?´ì ?«ìë¡?ë³??
        df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce')  # ë³?í  ???ë ê°ì NaN?¼ë¡ ì²ë¦¬
        df_processed[col] = df_processed[col].fillna(df_processed[col].median())

        # ?¬ë¼?´ë© ?ë???ì©
        data = df_processed[col].to_numpy()
        T = len(data)
        N = T - sliding_window_size + 1

        if N <= 0:
            continue

        sliding_windows = np.array([data[i:i + sliding_window_size] for i in range(N)])
        sliding_windows = np.mean(sliding_windows, axis=1)
        df_processed[col] = pd.Series(sliding_windows, index=df_processed.index[:len(sliding_windows)])

    # NaN ê°ì ì¤ìê°ì¼ë¡??ì²?
    df_processed = df_processed.fillna(df_processed.median())

    # 0ë²ì§¸ ?´ì ?¤ì ê²°í©?ì¬ ë°í
    df_processed.insert(0, first_col.name, first_col)

    return df_processed



def categorical_preprocess(df):
    # 0ë²ì§¸ ?´ì ?°ë¡ ???(?ë³¸ ?°ì´??ê·¸ë?ë¡??¬ì©)
    first_col = df.iloc[:, 0]

    # ?ë¨¸ì§ ?´ë§ ?ì²ë¦?ì§í
    df_processed = df.iloc[:, 1:].copy()
    
    label_encoders = {}
    for column in df_processed.columns:
        # Categorical ?´ì¸ì§ ?ì¸
        if df_processed[column].dtype == 'object' or pd.api.types.is_categorical_dtype(df_processed[column]):
            # LabelEncoderë¥??¬ì©??ë²ì£¼???°ì´?°ë? ?«ìë¡?ë³??
            le = LabelEncoder()
            df_processed[column] = le.fit_transform(df_processed[column])
            label_encoders[column] = le  # ?ì¤??ë³?í  ???¬ì©?????ëë¡????

    # 0ë²ì§¸ ?´ì ?¤ì ê²°í©?ì¬ ë°í
    df_processed.insert(0, first_col.name, first_col)

    return df_processed, label_encoders

def numerical_preprocess(df, tensor_rank):
    # 0ë²ì§¸ ?´ì ?°ë¡ ???(?ë³¸ ?°ì´??ê·¸ë?ë¡??¬ì©)
    first_col = df.iloc[:, 0]

    # ?ë¨¸ì§ ?´ë§ ?ì²ë¦?ì§í
    df_processed = df.iloc[:, 1:].copy()
    scaler = StandardScaler()

    for col in df_processed.columns:
        # ?ì? ?°ì´?ë¡ ë¬¶ì¸ ë¬¸ì?´ì ì²ë¦¬?ì¬ float?¼ë¡ ë³??
        if df_processed[col].dtype == object:  # ë¬¸ì?´ë¡ ?¸ì?ë ê²½ì°
            df_processed[col] = df_processed[col].str.replace("'", "").astype(float)

        # ?´ì´ numerical?¸ì? ?ì¸ (?«ì???´ë§ ?ì ë¶í´ ?ì©)
        if np.issubdtype(df_processed[col].dtype, np.number):
            data = df_processed[col].to_numpy().reshape(-1, 1)

            # ?°ì´???¤ì??¼ë§ ?ì©
            scaled_data = scaler.fit_transform(data)

            # ?ì ë¶í´ ?ì©
            tensor = tl.tensor(scaled_data)
            factors = parafac(tensor, rank=tensor_rank)
            reconstructed_tensor = tl.kruskal_to_tensor(factors)
            df_processed[col] = pd.Series(reconstructed_tensor.flatten(), index=df_processed.index)

        # NaN ê°?ì¤ìê°ì¼ë¡??ì²?(?«ì???´ë§)
        df_processed[col] = df_processed[col].fillna(df_processed[col].median())

    # 0ë²ì§¸ ?´ì ?¤ì ê²°í©?ì¬ ë°í
    df_processed.insert(0, first_col.name, first_col)

    return df_processed


# Prefect ?ì¤?? Celery???ì???ê¸°???¨ì
def get_streamlit_tenant_context():
    return {
        "tenant_id": st.session_state.get("tenant_id", "default"),
        "actor_id": st.session_state.get("actor_id", "streamlit-user"),
        "roles": st.session_state.get("roles", ["tenant_admin", "ml_operator", "viewer"]),
        "request_id": str(uuid.uuid4()),
        "plan_tier": st.session_state.get("plan_tier", "standard"),
    }


def _set_streamlit_auth_context(token: str):
    settings = get_auth_settings()
    claims = decode_token(token, settings)
    context = build_request_context(claims, request_id=None)
    st.session_state["tenant_id"] = context.tenant_id
    st.session_state["actor_id"] = context.actor_id
    st.session_state["roles"] = context.roles
    st.session_state["plan_tier"] = context.plan_tier
    st.session_state["auth_token"] = token
    st.session_state["auth_ready"] = True


def init_streamlit_auth_session():
    settings = get_auth_settings()
    if not settings.auth_enabled:
        st.session_state.setdefault("tenant_id", "default")
        st.session_state.setdefault("actor_id", "dev-user")
        st.session_state.setdefault("roles", ["tenant_admin", "ml_operator", "viewer"])
        st.session_state.setdefault("plan_tier", "standard")
        st.session_state["auth_ready"] = True
        return

    st.session_state.setdefault("auth_ready", False)
    with st.sidebar:
        st.subheader("Auth Session")
        token_input = st.text_input("Bearer Token", type="password", key="auth_token_input")
        if st.button("Apply Token"):
            try:
                _set_streamlit_auth_context(token_input.strip())
                st.success("Auth session initialized")
            except Exception as exc:  # noqa: BLE001
                st.session_state["auth_ready"] = False
                st.error(f"Auth failed: {exc}")

    if not st.session_state.get("auth_ready", False):
        st.warning("Authentication required. Set Bearer token in sidebar.")
        st.stop()


def require_streamlit_roles(allowed_roles):
    roles = set(st.session_state.get("roles", []))
    if "platform_admin" in roles or roles.intersection(set(allowed_roles)):
        return True
    st.error("Insufficient role. Required: tenant_admin or ml_operator")
    return False


def render_dashboard_panel():
    st.header("Dashboard", divider=True)
    try:
        data = fetch_dashboard_summary(
            token=st.session_state.get("auth_token"),
            request_id=str(uuid.uuid4()),
        )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to load dashboard summary: {exc}")
        return

    metrics = data.get("metrics", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Tasks", data.get("active_tasks", 0))
    c2.metric("Total(24h)", metrics.get("total", 0))
    c3.metric("Success Rate(24h)", f"{metrics.get('success_rate', 0)}%")
    c4.metric("Failures(24h)", metrics.get("failures", 0))

    st.subheader("Recent Tasks")
    tasks = data.get("recent_tasks", [])
    if tasks:
        st.dataframe(pd.DataFrame(tasks), use_container_width=True)
    else:
        st.info("No tasks found for this tenant.")


def render_operations_panel():
    st.header("Operations", divider=True)
    left, right = st.columns(2)

    with left:
        st.subheader("Quota")
        try:
            quota = fetch_quota_status(
                token=st.session_state.get("auth_token"),
                request_id=str(uuid.uuid4()),
            )
            st.json(quota)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Failed to load quota status: {exc}")

    with right:
        st.subheader("Audit Filters")
        limit = st.slider("Audit rows", min_value=10, max_value=300, value=100, step=10)
        action = st.text_input("Action (optional)", value="")

    st.subheader("Audit Events")
    try:
        audit_data = fetch_audit_events(
            token=st.session_state.get("auth_token"),
            limit=limit,
            action=action.strip() or None,
            request_id=str(uuid.uuid4()),
        )
        events = audit_data.get("events", [])
        if events:
            st.dataframe(pd.DataFrame(events), use_container_width=True)
        else:
            st.info("No audit events matched.")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to load audit events: {exc}")


def render_task_result_panel():
    st.header("Task Result", divider=True)
    task_id = st.text_input("Task ID", value="", key="task_result_task_id")
    if not task_id.strip():
        st.info("Enter a task_id to load result.")
        return

    token = st.session_state.get("auth_token")
    req_id = str(uuid.uuid4())

    col_load, col_causal, col_action = st.columns(3)
    load_result = col_load.button("Load Result")
    load_causal = col_causal.button("Load Causal Report")
    load_action = col_action.button("Load Recommendation")

    if load_result:
        try:
            result_data = fetch_task_result(task_id=task_id.strip(), token=token, request_id=req_id)
            status = result_data.get("status")
            st.subheader("Task Status")
            st.write(status)
            st.subheader("Task Payload")
            st.json(result_data)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Failed to load task result: {exc}")

    if load_causal:
        try:
            causal_data = fetch_causal_report(task_id=task_id.strip(), token=token, request_id=req_id)
            st.subheader("Causal Report")
            st.json(causal_data.get("causal_report", causal_data))
        except Exception as exc:  # noqa: BLE001
            st.error(f"Failed to load causal report: {exc}")

    if load_action:
        try:
            action_data = fetch_action_recommendation(task_id=task_id.strip(), token=token, request_id=req_id)
            st.subheader("Action Recommendation")
            st.json(action_data.get("action_recommendation", action_data))
        except Exception as exc:  # noqa: BLE001
            st.error(f"Failed to load action recommendation: {exc}")


@task(log_prints=True)
def submit_to_celery(df, algorithm, params, workflow_type, tenant_context):
    # API-first mode: Streamlit submits to FastAPI, and FastAPI enqueues Celery.
    task_id, trace_id = submit_task(
        df_records=df,
        algorithm=algorithm,
        params=params,
        token=st.session_state.get("auth_token"),
        request_id=tenant_context["request_id"],
    )
    return {"task_id": task_id, "trace_id": trace_id}

# Prefect ?ì¤?? Celery ?ì??ê²°ê³¼ë¥?ê°?¸ì¤???¨ì
@task(log_prints=True)
def get_celery_result(task_meta):
    return wait_for_task_result(
        task_id=task_meta["task_id"],
        token=st.session_state.get("auth_token"),
        request_id=task_meta["trace_id"],
    )

######## Time Series  ?°ì´??Prefect ?í¬?ë¡??########
@flow(log_prints=True)
def timeseries_workflow(df, algorithm, params, tenant_context):
    task_meta = submit_to_celery(df, algorithm, params, 'timeseries', tenant_context)
    result = get_celery_result(task_meta)
    return result

######## Categorical  ?°ì´??Prefect ?í¬?ë¡??########
@flow(log_prints=True)
def categorical_workflow(df, algorithm, params, tenant_context):
    task_meta = submit_to_celery(df, algorithm, params, 'categorical', tenant_context)
    result = get_celery_result(task_meta)
    return result

######## Numerical  ?°ì´??Prefect ?í¬?ë¡??########
@flow(log_prints=True)
def numerical_workflow(df, algorithm, params, tenant_context):
    task_meta = submit_to_celery(df, algorithm, params, 'numerical', tenant_context)
    result = get_celery_result(task_meta)
    return result


def extract_visualization_result(result):
    if isinstance(result, dict):
        payload = result.get("result")
        if isinstance(payload, dict):
            return payload
    return result

######## ?ê°??########
@flow
def visualization_flow(result, graph_type, x_column, y_column, df, start_handle=None, end_handle=None):
    create_visualizations(result, graph_type, x_column, y_column, df, start_handle, end_handle)

st.set_page_config(layout="wide")  # ?ë©´???ê² ?¬ì©
init_streamlit_auth_session()

# ?¸ì ?í ? ì? (CSV ?ì¼ ë°?ëª¨ë¸ ?¤í ?í ê´ë¦?
if 'uploaded_file' not in st.session_state:
    st.session_state.uploaded_file = None

# ì¿¼ë¦¬ ?ë¼ë¯¸í° ?ì¸
if 'model_run' not in st.session_state:
    st.session_state.model_run = False

# ê¸°ë³¸?ì¼ë¡ë Configuration ??§ ì¡´ì¬
if st.session_state.model_run:
    tabs = st.tabs(["Configuration Page", "Visualization Page"])
else:
    tabs = st.tabs(["Configuration Page"])

if __name__ == "__main__":
    with tabs[0]:
        # Streamlit ?¸í°?ì´??
        col1, col2 = st.columns(2)
        with col1:
            # st.set_page_config(page_title="AnomaliFlow: Distributed Execution of Reusable ML Workflows", page_icon=":material/edit:")
            st.title("AnomaliFlow")
            
            st.markdown("""
                        AnomaliFlow??ë¶ì° ?ê²½?ì ?¬ì¬??ê°?¥í ë¨¸ì ?¬ë ?í¬?ë¡?°ë? ?¤í?ê¸° ?í ê°ë ¥???êµ¬?ë?? ???ë«?¼ì? ë³µì¡??ë¨¸ì ?¬ë ?ì´?ë¼?¸ì ?ì½ê²?êµ¬ì±?ê³ , ?´ë? ?¬ë¬ ì»´í¨???¸ë??ë¶ì°?ì¬ ë¹ ë¥´ê²?ì²ë¦¬?????ëë¡??ìµ?ë¤. ?¤ì???°ì´?°ìê³?ë¨¸ì ?¬ë ëª¨ë¸???¨ê³¼?ì¼ë¡?ê²°í©?ê³ , ? ì°???¤í??ê°?¥íê²??ì¬ ?¬ì©?ìê²??ì? ?ì°?±ì ?ê³µ?©ë??

                        ì£¼ì ê¸°ë¥:
                        - **ë¶ì° ì»´í¨??ì§??*: ?¬ë¬ ?¸ë?ì ë³ë ¬ ì²ë¦¬ë¥??µí´ ??©ë ?°ì´??ë°?ë³µì¡??ëª¨ë¸??ë¹ ë¥´ê²?ì²ë¦¬ ê°?¥í©?ë¤.
                        - **?í¬?ë¡???¬ì¬?©ì±**: ë°ë³µ?ì¸ ?ì???ë?íê³? ?¤ì???ê²½?ì???ì¼???í¬?ë¡?°ë? ?½ê² ?¬ì¬?©í  ???ìµ?ë¤.
                        - **?ì¥??*: ?¤ì??ML ?ë ?ì??ë°??´ê³¼???µí©??ì§?í???ì¥?±ê³¼ ? ì°?±ì ?ê³µ?©ë??

                        ???ë«?¼ì ?µí´ ë³´ë¤ ?¨ì¨?ì´ê³?ê°í¸??ë¨¸ì ?¬ë ê°ë°??ê²½í?´ë³´?¸ì.
                        """)
            # sidebar
            with st.sidebar:
                st.title("AnomaliFlow")
                st.markdown("""
                            Distributed Execution of Reusable ML Workflows
                            """)
                st.divider()
                st.header("?» ì£¼ì ê¸°ë¥")
                stage = st.sidebar.button('About')
                                        
                st.header("??ML Models") 
                stage = st.sidebar.button('Supported ML Models')

                # http://localhost:4200/dashboard ????°ë
                st.header("? Workflow Management")
                stage = st.sidebar.radio("Choose Step", ['Home', 'Saved Workflows', 'Task Result', 'Monitor Workflows'])

                st.header("ë§ë  ?¬ë")
                stage = st.sidebar.button('Our team')
                

            if stage == "Saved Workflows":
                render_dashboard_panel()
                st.stop()

            if stage == "Task Result":
                render_task_result_panel()
                st.stop()

            if stage == "Monitor Workflows":
                render_operations_panel()
                st.stop()

            st.header("Data import" )
            uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

            st.header("Jobs for Executing Distributed Task", divider=True)
            n_jobs = st.slider("Select n_jobs", min_value=1, max_value=6, value=2)

            st.write(f"n_jobs: {n_jobs}")

            if uploaded_file is not None:
                df = pd.read_csv(uploaded_file, encoding="UTF-8")
                st.write(df)

                # Detect data types
                data_type = classify_dataset(df)
                st.write(data_type)
                with col2:        
                    st.header(f"Type of the Dataset: {data_type.capitalize()}", divider=True)
                    
                    model_selections = {}

                    # Time Series Data
                    if data_type == 'time_series':
                        
                        st.subheader(f"Model Configuration", divider=True)
                        # Hyper-parameters for Tensor Decomposition and Window Operation
                        tensor_rank = st.slider("Tensor Rank", min_value=1, max_value=10, value=3)
                        sliding_window_size = st.slider("Sliding Window Size", min_value=2, max_value=50, value=5)

                        # Data Preprocessing
                        df = timeseries_preprocess(df, tensor_rank, sliding_window_size)

                        # Model Selection
                        time_series_model = st.selectbox("Select a Model", ["IsolationForest", "GMM"])
                        
                        
                        # # ?ë°©???¬ë¼?´ë
                        # preview_handle_range = st.slider(
                        #     "Filtering range for data points", 
                        #     1, len(df), 
                        #     value=(1, 1500)  # ì´ê¸°ê°?ë²ì ?¤ì  (?ì?? ?ì )
                        # )

                        # # ????í°ë§?
                        # start_handle, end_handle = map(int, preview_handle_range)
                        # selected_data = df[start_handle:end_handle]

                        # # threshold_handle = st.slider("Threshold", 0.0, 1.0, value=0.5)
                        
                        params = {}
                        if time_series_model == "IsolationForest":
                            params['max_samples'] = st.number_input("The maximum number of samples", 1, len(df))
                            params['n_estimators'] = st.number_input("The number of estimators", 1, 1000, value=100)
                            params['contamination'] = st.number_input("The contamination parameter", 0.0, 0.5, value=0.1)
                            params['n_jobs'] = n_jobs
                        elif time_series_model == "GMM":
                            params['n_init'] = st.slider("The number of times for the GMM execution with different certroid seeds", min_value=1, max_value=10, value=1)
                            params['n_components'] = st.number_input("The number of components", 1, len(df), value=2)
                            # params['covariance_type'] = st.selectbox("Covariance type", ["full", "tied", "diag", "spherical"], index=0)
                            params['random_state'] = st.number_input("Random state", 0, 1000, value=42)
                            params['init_params'] = 'kmeans'
                        
                        st.subheader(f"Visualization", divider=True)
                        graph_type = st.selectbox("Select a Graph Type", ["Line Graph", "Scatter Plot", "Bar Graph"])
                        columns = df.columns.tolist()
                        columns = [col for col in df.columns if col != 'date']
                        x_column = st.selectbox("Select X-axis Feature", columns)
                        y_column = st.selectbox("Select Y-axis Feature", columns)
                        
                        if st.button("Run your workflow"):
                            if not require_streamlit_roles({"tenant_admin", "ml_operator"}):
                                st.session_state.model_run = False
                            else:
                                st.session_state.model_run = True
                            if len(tabs) > 1 and st.session_state.model_run:
                                with tabs[1]:
                                    st.title("AnomaliFlow Visualization")
                                    # Celery worker??ë¹ëê¸??ì ?ì²­
                                    df_dict = df.to_dict(orient='records')
                                    result = timeseries_workflow(
                                        df_dict,
                                        time_series_model,
                                        params,
                                        get_streamlit_tenant_context(),
                                    )
                                    
                                    # Visualization step
                                    if result:
                                        st.write("Workflow Completed! Visualizing Results...")
                                        viz_result = extract_visualization_result(result)
                                        # Call visualization function
                                        visualization_flow(viz_result, graph_type, x_column, y_column, df, None, None)
                                        st.write(result)
                                        #visualization_flow(result, graph_type, x_column, y_column, df, start_handle, end_handle)    
                    
                    # Categorical Data
                    elif data_type == 'categorical':
                        
                        st.subheader(f"Model Configuration", divider=True)
                        # Data Preprocessing
                        df, label_encoders = categorical_preprocess(df)

                        # Algorithm select (?°ì´??? íë³ë¡ ?¤ë¥´ê²?
                        algorithm = st.selectbox("Select a Model", ["DBSCAN", "LOF"])

                        # threshold_handle = st.slider("Threshold", 0.0, 1.0, value=0.5)

                        # parameters
                        params = {}
                        if algorithm == "DBSCAN":
                            eps = st.slider("epsilon(?)", min_value=0.01, max_value=10.00, value=0.05)
                            min_samples = st.slider("The mininum number of samples", min_value=1, max_value=100, value=5)
                            params = {"eps": eps, "min_samples": min_samples, "n_jobs" : n_jobs}
                        elif algorithm == "LOF":
                            params['n_neighbors'] = st.number_input("The number of neighbors", 1, 100, value=20)
                            params['contamination'] = st.number_input("The contamination parameter", 0.0, 0.5, value=0.1)
                            params['n_jobs'] = n_jobs


                        st.subheader(f"Visualization", divider=True)
                        graph_type = st.selectbox("Select a Type of Chart ", ["Line Graph", "Scatter Plot", "Bar Graph", "Scatter Plot (Jittered)"])
                        columns = df.columns.tolist()
                        x_column = st.selectbox("Select X-axis Feature", columns)
                        y_column = st.selectbox("Select Y-axis Feature", columns)

                        if st.button("Run your workflow"):
                            if not require_streamlit_roles({"tenant_admin", "ml_operator"}):
                                st.session_state.model_run = False
                            else:
                                st.session_state.model_run = True
                            if st.session_state.model_run:
                                with tabs[1]:
                                    st.title("AnomaliFlow Visualization")
                                    # Celery worker??ë¹ëê¸??ì ?ì²­
                                    df_dict = df.to_dict(orient='records')
                                    result = categorical_workflow(
                                        df_dict,
                                        algorithm,
                                        params,
                                        get_streamlit_tenant_context(),
                                    )
                                    
                                    # Visualization step
                                    if result:
                                        st.write("Workflow Completed! Visualizing Results...")
                                        st.write(result)
                                        viz_result = extract_visualization_result(result)
                                        # Call visualization function
                                        visualization_flow(viz_result, graph_type, x_column, y_column, df, None, None)

                    # Numerical Data
                    if data_type == 'numerical':
                        
                        st.subheader(f"Model Configuration", divider=True)
                        # Hyper-parameters for Tensor Decomposition 
                        tensor_rank = st.slider("Tensor Rank", min_value=1, max_value=10, value=1)

                        # Data Preprocessing
                        df = numerical_preprocess(df, tensor_rank)

                        # Model Selection
                        numerical_model = st.selectbox("Select a Model", ["IsolationForest", "GMM", "DBSCAN", "LOF", "KMeans"])

                        # threshold_handle = st.slider("Threshold", 0.0, 1.0, value=0.5)
                        
                        params = {}
                        if numerical_model == "IsolationForest":
                            params['max_samples'] = st.number_input("The maximum number of samples", 1, len(df))
                            params['n_estimators'] = st.number_input("The number of estimators", 1, 1000, value=100)
                            params['contamination'] = st.number_input("The contamination parameter", 0.0, 0.5, value=0.1)
                            params['n_jobs'] = n_jobs
                        elif numerical_model == "GMM":
                            params['n_init'] = st.slider("The number of times for the GMM execution with different certroid seeds", min_value=1, max_value=10, value=1)
                            params['n_components'] = st.number_input("The number of components", 1, len(df), value=2)
                            # params['covariance_type'] = st.selectbox("Covariance type", ["full", "tied", "diag", "spherical"], index=0)
                            params['random_state'] = st.number_input("Random state", 0, 1000, value=42)
                            params['init_params'] = 'kmeans'
                        elif numerical_model == "DBSCAN":
                            eps = st.slider("epsilon(?)", min_value=0.01, max_value=10.00, value=0.05)
                            min_samples = st.slider("The mininum number of samples", min_value=1, max_value=100, value=5)
                            params = {"eps": eps, "min_samples": min_samples, "n_jobs" : n_jobs}
                        elif numerical_model == "LOF":
                            params['n_neighbors'] = st.number_input("The number of neighbors", 1, 100, value=20)
                            params['contamination'] = st.number_input("The contamination parameter", 0.0, 0.5, value=0.1)
                            params['n_jobs'] = n_jobs
                        elif numerical_model == "KMeans":
                            n_clusters = st.slider("The number of clusters", min_value=2, max_value=20, value=3)
                            n_init = st.slider("The number of times for the KMeans execution with different certroid seeds", min_value=1, max_value=20, value=10)
                            params = {"n_clusters": n_clusters, "n_init": n_init, "n_jobs" : n_jobs}

                    
                        
                        st.subheader(f"Visualization", divider=True)
                        graph_type = st.selectbox("Select a Graph Type", ["Line Graph", "Scatter Plot", "Bar Graph"])
                        columns = df.columns.tolist()
                        x_column = st.selectbox("Select X-axis Feature", columns)
                        y_column = st.selectbox("Select Y-axis Feature", columns)
                        
                        if st.button("Run your workflow"):
                            if not require_streamlit_roles({"tenant_admin", "ml_operator"}):
                                st.session_state.model_run = False
                            else:
                                st.session_state.model_run = True
                            if st.session_state.model_run:
                                with tabs[1]:
                                    st.title("AnomaliFlow Visualization")
                                    # Celery worker??ë¹ëê¸??ì ?ì²­
                                    df_dict = df.to_dict(orient='records')
                                    result = numerical_workflow(
                                        df_dict,
                                        numerical_model,
                                        params,
                                        get_streamlit_tenant_context(),
                                    )
                                    
                                    # Visualization step
                                    if result:
                                        st.write("Workflow Completed! Visualizing Results...")
                                        st.write(result)
                                        viz_result = extract_visualization_result(result)
                                        # Call visualization function
                                        visualization_flow(viz_result, graph_type, x_column, y_column, df, None, None)

