#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Low-quality evidence recovery dynamics analysis
=======================

This script analyzes the recovery behavior of agents when encountering low-quality evidence, showing the exit speed of different actions through risk curves.
Main findings: Refine/Follow-up + grounded assessment accelerates exit; Repeat stagnates. This pattern reproduces in different settings.

Usage:
python recovery.py [input_file] [output_dir]
"""

import os
import json
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict, Counter
import warnings
warnings.filterwarnings('ignore')

# Try to import survival analysis library
try:
    from lifelines import KaplanMeierFitter
    LIFELINES_AVAILABLE = True
except ImportError:
    print("Warning: lifelines library is not installed, will skip survival analysis. Use pip install lifelines to install.")
    LIFELINES_AVAILABLE = False

# Set plotting style
sns.set_theme(context='paper', style='whitegrid', palette='colorblind', font_scale=1.1)
plt.rcParams.update({
    'figure.dpi': 200,
    'savefig.dpi': 300,
    'axes.titlesize': 12,
    'axes.labelsize': 10,
    'legend.fontsize': 9,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
})

# Global model color palette (shared with groundness analysis for consistency)
MODEL_COLOR_PALETTE = {
    'Base (Qwen)': '#460057',          
    'Few-shot (Qwen)': '#423e81',      
    'CoT (Qwen)': '#8b5a9f',
    'ReAct (Qwen)': '#a67db8',
    'Structured (Qwen)': '#c19fd1',
    'Self-Consistency (Qwen)': '#d9bce5',
    'GPT-5': '#e74c3c',
    'GPT-4o': '#e67e22',
    'Tongyi DeepResearch': '#3498db',
    'Claude Sonnet 4.5': '#9b59b6',
    'Qwen3-30B-A3B': '#1abc9c',
    'DeepResearcher': '#2e5d88',       
    'ReSearch': '#159988',             
    'SearchR1': '#6ece5d',            
    'ASearcher': '#fee837',           
}
def get_model_color(model_name: str) -> str:
    return MODEL_COLOR_PALETTE.get(model_name, '#7f7f7f')

# 定义常量
ACTION_COLORS = {
    'Refine': '#1f77b4',
    'Follow-up': '#2ca02c',
    'Repeat': '#d62728',
    'Grounded reasoning': '#ff7f0e'
}

# ---------- Evidence mapping & turn-level action taxonomy (aligned with R3) ----------
def map_evidence_level(information_quality: str, information_clarity: str) -> int:
    """E=0: IQ!=Sufficient; E=1: IQ=Sufficient & IC!=Clear; E=2: IQ=Sufficient & IC=Clear"""
    iq = (information_quality or '').strip()
    ic = (information_clarity or '').strip()
    if iq == 'Sufficient':
        return 2 if ic == 'Clear' else 1
    return 0

def classify_action_for_turn(ann: dict, category: str = None) -> str:
    """Coarse action taxonomy for turn-level analyses.
    Returns one of: 'Refine','Follow-up','Repeat','Grounded reasoning','Answer','Other'.
    """
    if not isinstance(ann, dict):
        return 'Other'
    t = ann.get('type')
    if t in ('CorrectAnswer','IncorrectAnswer'):
        return 'Answer'
    if t == 'RefinedQuery':
        return 'Refine'
    if t == 'FollowUpQuery':
        return 'Follow-up'
    if t == 'RepeatQuery':
        return 'Repeat'
    
    is_reasoning_step = False
    if t in ('StateAssessment','PlanFormation','InformationSynthesis'):
        is_reasoning_step = True
    # For DeepResearch, InitialQuery/NewQuery are also considered reasoning
    elif category == 'DeepResearch' and t in ('InitialQuery', 'NewQuery', 'Query'):
        is_reasoning_step = True
    
    if is_reasoning_step:
        attrs = ann.get('attributes', {}) or {}
        grounding = str(attrs.get('groundness', '')).lower()
        if grounding == 'grounded':
            return 'Grounded reasoning'
    return 'Other'

def build_turn_level_records(traces):
    """Per-turn records with cumulative E and action label.
    Fields: model, category, dataset, question_id, step_index, E, action, is_answer
    """
    rows = []
    for t in traces:
        model, cat = clean_and_categorize_model(t.get('model', ''))
        if cat == 'Other':
            continue
        dataset = t.get('dataset', 'Unknown')
        qid = t.get('question_id', t.get('id', None))
        if qid is None:
            qid = t.get('question', None)
        steps = t.get('trace', []) or []
        cur_E = 0
        answered = False
        for i, step in enumerate(steps):
            ann = step.get('annotation', {})
            if isinstance(ann, dict) and ann.get('type') == 'search_result':
                attrs = ann.get('attributes', {}) or {}
                cur_E = max(cur_E, map_evidence_level(attrs.get('information_quality'), attrs.get('information_clarity')))
            action = classify_action_for_turn(ann, category=cat)
            is_answer = 1 if (action == 'Answer' and not answered) else 0
            if is_answer:
                answered = True
            rows.append({
                'model': model,
                'category': cat,
                'dataset': dataset,
                'question_id': qid,
                'step_index': i,
                'E': cur_E,
                'action': action,
                'is_answer': is_answer
            })
            if answered:
                break
    return pd.DataFrame(rows)



def analyze_pillar3_recovery_dynamics(turn_df, output_dir, horizon=20):
    print("\n=== R1-A3: Trajectory-level recovery dynamics ===")
    # Build per-trajectory first-hit table (do NOT mix models)
    rows = []
    for (model, cat, ds, qid), g in turn_df.groupby(['model','category','dataset','question_id']):
        g = g.sort_values('step_index')
        steps = g['step_index'].values
        Es = g['E'].values
        hit_idx = np.where(Es >= 2)[0]
        first_hit = int(steps[hit_idx[0]]) if hit_idx.size else np.nan
        rows.append({'category': cat, 'dataset': ds, 'question_id': qid, 'model': model, 'first_hit_E2': first_hit})
    traj = pd.DataFrame(rows)

    # Print per-category stats
    stats_rows = []
    # Get actual categories from data
    actual_categories = sorted(traj['category'].dropna().unique().tolist())
    for cat in actual_categories:
        sub = traj[traj['category']==cat]
        if sub.empty: continue
        ever = sub['first_hit_E2'].notna().mean()
        median_turn = sub['first_hit_E2'].median() if sub['first_hit_E2'].notna().any() else np.nan
        print(f"  - {cat}: % reach E=2 = {ever:.3f}, median turn = {median_turn}")
        stats_rows.append({'category': cat, 'pct_reach_E2': ever, 'median_first_hit': median_turn, 'n_traces': len(sub)})

    # Print per-trained-model stats (for RL Agents and Prompting Variants)
    trained_categories = ['RL Agents', 'Prompting Variants']
    trained_models = []
    for cat in trained_categories:
        if cat in actual_categories:
            trained_models.extend(sorted(traj[traj['category']==cat]['model'].dropna().unique().tolist()))
    for m in trained_models:
        subm = traj[traj['model']==m]
        if subm.empty: continue
        ever = subm['first_hit_E2'].notna().mean()
        median_turn = subm['first_hit_E2'].median() if subm['first_hit_E2'].notna().any() else np.nan
        print(f"    · {m}: % reach E=2 = {ever:.3f}, median turn = {median_turn}")

    stats = pd.DataFrame(stats_rows)
    stats_csv = os.path.join(output_dir, 'R1_A3_recovery_trajectory_stats.csv')
    stats.to_csv(stats_csv, index=False)
    print(f"[A3] Saved stats CSV: {stats_csv}")

    # Plot: All models with bootstrapped CIs
    fig, ax = plt.subplots(figsize=(9,5))
    rng = np.random.default_rng(42)
    n_boot = 1000      
    # Create list of all models to plot - include all models from data
    base_models = []
    if 'Base' in actual_categories:
        base_models.append('Base (Qwen)')
    if 'Few-shot' in actual_categories:
        base_models.append('Few-shot (Qwen)')
    
    # Get all models from data, preserving order
    all_models_present = sorted(traj['model'].dropna().unique().tolist())
    all_models = base_models + all_models_present
    
    for i, m in enumerate(all_models):
        # Handle both category-based and model-based data
        if m in ['Base (Qwen)', 'Few-shot (Qwen)']:
            # For Base and Few-shot, use category-based filtering
            cat = 'Base' if m == 'Base (Qwen)' else 'Few-shot'
            sub = traj[traj['category']==cat]
            linewidth = 2.5
            alpha = 0.2
        else:
            # For all other models, use model-based filtering (works for both RL Agents and Prompting Variants)
            sub = traj[traj['model']==m]
            linewidth = 1.5
            alpha = 0.15
            
        if sub.empty:
            print(f"  Warning: No data for model {m}, skipping")
            continue
            
        xs = list(range(0, horizon+1))
        vals = sub['first_hit_E2'].values
        # Handle NaN as not reached within horizon
        reached_matrix = np.array([(vals <= t) for t in xs])  # shape: (T, N)
        # Point estimate
        ys = np.nanmean(reached_matrix, axis=1)
        ax.plot(xs, ys, label=m, color=get_model_color(m), linewidth=linewidth)
        try:
            ax.text(xs[-1] + 0.1, ys[-1], m, color=get_model_color(m),
                    fontsize=8, va='center')
        except Exception:
            pass
        
        # Bootstrap CI over traces
        N = reached_matrix.shape[1]
        if N > 1:
            idx = rng.integers(0, N, size=(n_boot, N))
            lows = []
            highs = []
            # Compute bootstrap distribution per t
            for row in reached_matrix:
                # row shape (N,)
                boots = row[idx]
                means = boots.mean(axis=1)
                lo, hi = np.percentile(means, [2.5, 97.5])
                lows.append(lo)
                highs.append(hi)
            ax.fill_between(xs, lows, highs, color=get_model_color(m), alpha=alpha, linewidth=0)

    ax.set_xlim(0, horizon + 1.5)
    ax.set_xlabel('Turn'); ax.set_ylabel('Frac. traces reached E=2'); ax.set_ylim(0,1)
    ax.set_title('R1-A3: CDF of reaching E=2 by turn')
    ax.grid(True, alpha=0.3); ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left')
    plt.tight_layout()
    savefig(fig, output_dir, 'fig_R1_A3_recovery_cdf')


# --- Helper for clustered bootstrap of ratios (per question clustering) ---
def clustered_ratio_ci(numer_by_cluster, denom_by_cluster, n_boot=5000, seed=42):
    """Compute bootstrap CI for ratio of sums over clusters.
    numer_by_cluster, denom_by_cluster: dict cluster_id -> float
    Returns (point, lo, hi)
    """
    clusters = list(denom_by_cluster.keys())
    if not clusters:
        return 0.0, 0.0, 0.0
    numer = np.array([float(numer_by_cluster.get(c, 0.0)) for c in clusters])
    denom = np.array([float(denom_by_cluster.get(c, 0.0)) for c in clusters])
    point = float(numer.sum()) / float(denom.sum()) if float(denom.sum()) > 0 else 0.0
    rng = np.random.default_rng(seed)
    n = len(clusters)
    idx = rng.integers(0, n, size=(n_boot, n))
    samp = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        sel = idx[i]
        num_b = float(numer[sel].sum())
        den_b = float(denom[sel].sum())
        samp[i] = (num_b/den_b) if den_b>0 else np.nan
    lo, hi = float(np.nanpercentile(samp, 2.5)), float(np.nanpercentile(samp, 97.5))
    return point, lo, hi

def ensure_dir(path):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)

def savefig(fig, output_dir, name):
    """保存图表为PNG"""
    # 确保目录存在
    ensure_dir(output_dir)
    
    png_path = os.path.join(output_dir, f'{name}.png')
    
    fig.tight_layout()
    fig.savefig(png_path)
    print(f"Saved {png_path}")
    plt.close(fig)

def clean_and_categorize_model(model_name):
    """清理模型名称并分类"""
    if not isinstance(model_name, str):
        return "Unknown", "Other"
        
    # New DeepResearch models
    if "gpt-5" in model_name or model_name == "gpt-5":
        return "GPT-5", "DeepResearch"
    if "gpt-4o" in model_name or model_name == "gpt-4o":
        return "GPT-4o", "DeepResearch"
    if "tongyi-deepresearch" in model_name or "alibaba-tongyi-deepresearch" in model_name:
        return "Tongyi DeepResearch", "DeepResearch"
    if "claude-sonnet-4-5-thinking" in model_name or "claude-sonnet-4-5-thinking-all" in model_name:
        return "Claude Sonnet 4.5", "DeepResearch"
    if "Qwen3-30B-A3B-Instruct-2507" in model_name or "Qwen3-30B-A3B" in model_name:
        return "Qwen3-30B-A3B", "DeepResearch"
    
    # Legacy models
    if "fewshot-Qwen2.5-7B-Instruct" in model_name:
        return "Few-shot (Qwen)", "Few-shot"
    if "cot-Qwen2.5-7B-Instruct" in model_name:
        return "CoT (Qwen)", "Prompting Variants"
    if "react-Qwen2.5-7B-Instruct" in model_name:
        return "ReAct (Qwen)", "Prompting Variants"
    if "structured-Qwen2.5-7B-Instruct" in model_name:
        return "Structured (Qwen)", "Prompting Variants"
    if "self_consistency-Qwen2.5-7B-Instruct" in model_name:
        return "Self-Consistency (Qwen)", "Prompting Variants"
    if "Qwen2.5-7B-Instruct" in model_name:
        return "Base (Qwen)", "Base"
    if "SearchR1" in model_name:
        return "SearchR1", "RL Agents"
    if "DeepResearcher" in model_name:
        return "DeepResearcher", "RL Agents"
    if "ReSearch" in model_name:
        return "ReSearch", "RL Agents"
    if "ASearcher" in model_name:
        return "ASearcher", "RL Agents"
    return "Other", "Other"

def load_traces(path):
    """加载并解析JSONL轨迹数据"""
    traces = []
    with open(path, 'r') as f:
        for line in f:
            try:
                traces.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return traces


def detect_low_quality_episodes(traces):
    """
    检测低质量证据片段(LQE)
    
    开始: search_result.information_quality=Insufficient 或 information_clarity≠Clear
    结束: information_quality=Sufficient 且 information_clarity=Clear，或 CorrectAnswer
    """
    episodes = []
    
    for trace in traces:
        model, cat = clean_and_categorize_model(trace.get('model', ''))
        if cat == 'Other':
            continue
            
        dataset = trace.get('dataset', 'Unknown')
        question_id = trace.get('question_id', trace.get('id', 'unknown'))
        # approximate question length by whitespace tokens
        q_text = str(trace.get('question', ''))
        question_len = len(q_text.split()) if q_text else 0
        
        # 扫描寻找LQE开始点
        in_episode = False
        episode = {'model': model, 'category': cat, 'dataset': dataset, 
                   'question_id': question_id, 'question_len': question_len, 'steps': []}
        
        for i, step in enumerate(trace.get('trace', [])):
            ann = step.get('annotation', {})
            if not isinstance(ann, dict):
                continue
                
            # 检查是否是搜索结果
            if ann.get('type') == 'search_result':
                quality = ann.get('attributes', {}).get('information_quality', '')
                clarity = ann.get('attributes', {}).get('information_clarity', '')
                
                # 开始低质量片段
                if not in_episode and (quality == 'Insufficient' or clarity != 'Clear'):
                    in_episode = True
                    episode['start_idx'] = i
                    episode['steps'].append({
                        'idx': i, 
                        'action': 'Start',
                        'clarity': clarity  # 保存清晰度信息
                    })
                
                # 可能的退出条件之一
                elif in_episode and quality == 'Sufficient' and clarity == 'Clear':
                    episode['steps'].append({'idx': i, 'action': 'Exit', 'reason': 'Sufficient&Clear'})
                    episode['end_idx'] = i
                    episode['censored'] = 0
                    episodes.append(episode)
                    
                    # 重置为新片段
                    in_episode = False
                    episode = {'model': model, 'category': cat, 'dataset': dataset, 
                               'question_id': question_id, 'question_len': question_len, 'steps': []}
            
            # 另一个退出条件：正确答案
            elif in_episode and ann.get('type') == 'CorrectAnswer':
                episode['steps'].append({'idx': i, 'action': 'Exit', 'reason': 'CorrectAnswer'})
                episode['end_idx'] = i
                episode['censored'] = 0
                episodes.append(episode)
                
                # 重置为新片段
                in_episode = False
                episode = {'model': model, 'category': cat, 'dataset': dataset, 
                           'question_id': question_id, 'question_len': question_len, 'steps': []}
            
            # 如果在片段中，记录行动
            elif in_episode:
                action = classify_recovery_action(step, category=cat)
                if action:
                    episode['steps'].append({'idx': i, 'action': action, 'raw_type': ann.get('type')})
        
        # 处理被截断的片段
        if in_episode:
            episode['end_idx'] = len(trace.get('trace', [])) - 1
            episode['censored'] = 1
            episodes.append(episode)
    
    # 打印每个类别和模型的片段数量
    model_counts = defaultdict(int)
    category_counts = defaultdict(int)
    
    for episode in episodes:
        model_counts[episode['model']] += 1
        category_counts[episode['category']] += 1
    
    print("Number of detected low-quality evidence segments:")
    print("By category:")
    for category, count in category_counts.items():
        print(f"  {category}: {count}")
    
    print("By model:")
    for model, count in sorted(model_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {model}: {count}")
    
    return episodes

def classify_recovery_action(step, category: str = None):
    """将步骤分类为恢复行动之一"""
    ann = step.get('annotation', {})
    if not isinstance(ann, dict):
        return None
        
    action_type = ann.get('type')
    
    # 查询类型行动
    if action_type == 'RefinedQuery':
        return 'Refine'
    elif action_type == 'FollowUpQuery':
        return 'Follow-up'
    elif action_type == 'RepeatQuery':
        return 'Repeat'
    
    
    is_reasoning_step = False
    if action_type in ('StateAssessment', 'PlanFormation', 'InformationSynthesis'):
        is_reasoning_step = True
    elif category == 'DeepResearch' and "Query" in action_type:
        is_reasoning_step = True
        
    if is_reasoning_step:
        grounding = str(ann.get('attributes', {}).get('groundness', '')).lower()
        if grounding == 'grounded':
            return 'Grounded reasoning'
    
    return None


def build_action_occurrences(episodes):
    """Expand episodes into per-action occurrences with time-to-exit from the action.
    Returns list of dicts: {model, category, dataset, question_id, action, idx, tte, event, episode_censored}
    - tte: steps from the action to Exit (or to episode end if censored)
    - event: 1 if Exit observed after the action, else 0
    """
    rows = []
    for ep in episodes:
        steps = ep['steps']
        # locate Exit step index in absolute step idx space
        exit_abs_idx = None
        for st in steps:
            if st['action'] == 'Exit':
                exit_abs_idx = st['idx']
                break
        for st in steps:
            a = st['action']
            if a in ('Start','Exit'):
                continue
            cur_idx = st['idx']
            if exit_abs_idx is not None and exit_abs_idx > cur_idx:
                tte = exit_abs_idx - cur_idx
                event = 1
            else:
                # censored at episode end
                tte = ep['end_idx'] - cur_idx
                event = 0
            rows.append({
                'model': ep['model'],
                'category': ep['category'],
                'dataset': ep['dataset'],
                'question_id': ep['question_id'],
                'action': a,
                'idx': cur_idx,
                'tte': max(0, tte),
                'event': event,
                'episode_censored': ep.get('censored', 0),
                'raw_type': st.get('raw_type')
            })
    return pd.DataFrame(rows)


def analyze_km_after_action(episodes, output_dir, min_n=20):
    """Kaplan–Meier survival of time-to-exit aligned at action occurrences (not only first action).
    Use 'Grounded reasoning' that aggregates all reasoning types: StateAssessment, PlanFormation, InformationSynthesis.
    Requires lifelines.
    """
    if not LIFELINES_AVAILABLE:
        print("Skipping action-aligned survival analysis, lifelines library not installed")
        return None
    df = build_action_occurrences(episodes)
    if df.empty:
        print("No action occurrences for KM-after-action analysis.")
        return None
    # Remap actions for KM strictly from labeled actions in episodes.
    # Grounded reasoning only if the episode step was labeled as such (i.e., directly grounded).
    def map_km_action(row):
        if row['action'] in ('Refine','Follow-up','Repeat','Grounded reasoning'):
            return row['action']
        return 'Other'
    df['km_action'] = df.apply(map_km_action, axis=1)
    # Report counts
    print("[KM-after-action] Occurrence counts by km_action:")
    print(df['km_action'].value_counts())
    fig, ax = plt.subplots(figsize=(10,6))
    for action in ['Refine','Follow-up','Grounded reasoning','Repeat']:
        sub = df[df['km_action']==action]
        if len(sub) < min_n:
            print(f"  - Skip {action}: n={len(sub)} < {min_n}")
            continue
        print(f"  - Plot {action}: n={len(sub)} events={int(sub['event'].sum())}")
        kmf = KaplanMeierFitter()
        kmf.fit(sub['tte'], event_observed=sub['event'], label=action)
        kmf.plot_survival_function(ax=ax, color=ACTION_COLORS.get(action,'gray'))
    ax.set_xlabel('Steps since action')
    ax.set_ylabel('P(remaining in LQE)')
    ax.set_title('Time to Exit — aligned at action occurrences (Grounded reasoning aggregated)')
    savefig(fig, output_dir, 'fig2b_km_after_action')
    return fig

def main():
    parser = argparse.ArgumentParser(description='分析低质量证据恢复动力学')
    parser.add_argument('input_file', nargs='?', default='final_annotated_traces.jsonl',
                      help='输入的轨迹JSONL文件')
    parser.add_argument('output_dir', nargs='?', default='recovery_figs',
                      help='输出图表的目录')
    args = parser.parse_args()
    
    # 确保输出目录存在
    ensure_dir(args.output_dir)
    
    print(f"Loading trajectory data: {args.input_file}")
    traces = load_traces(args.input_file)
    print(f"Loaded {len(traces)} trajectories")
    
    print("Detecting low-quality evidence segments...")
    episodes = detect_low_quality_episodes(traces)
    print(f"找到 {len(episodes)} 个低质量证据片段")
    
    # Quick episode summary
    ep_by_cat = Counter([e['category'] for e in episodes])
    ep_by_data = Counter([e['dataset'] for e in episodes]).most_common(10)
    print("片段摘要: 每类别计数:")
    for k,v in ep_by_cat.items():
        print(f"  - {k}: {v}")
    print("片段摘要: Top10 数据集:")
    for k,v in ep_by_data:
        print(f"  - {k}: {v}")

    if LIFELINES_AVAILABLE:
        print("按行动对齐的生存分析 (更稳健)...")
        analyze_km_after_action(episodes, args.output_dir)
    # Recovery as competence: A3 only
    print("\n围绕复原力(Recovery)的能力视角分析：A3")
    turn_df = build_turn_level_records(traces)
    # Save raw turn-level table for auditing
    turns_csv = os.path.join(args.output_dir, 'R1_turn_level_records.csv')
    turn_df.to_csv(turns_csv, index=False)
    print(f"[R1] Saved turn-level records: {turns_csv}")
    analyze_pillar3_recovery_dynamics(turn_df, args.output_dir)
    
    print(f"分析完成。保留的图表已保存到 {args.output_dir}/")

if __name__ == '__main__':
    main()