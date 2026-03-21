#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unpaired evaluation across all available models (no BASE/RL filtering)
 - Metrics:
  RQI: Reasoning Quality Index = fraction of reasoning steps (InformationSynthesis, PlanFormation, StateAssessment) with groundness=Directly Grounded
  SEI components:
    - Turns-to-First-Sufficient (lower=better), with sensitivity toggle for Sufficient&Clear vs Sufficient-only
    - RefinedQuery rate = (#RefinedQuery) / (#search query turns)
    - RepeatQuery rate = (#RepeatQuery) / (#search query turns)
  Outcomes:
    - Success rate (CorrectAnswer / is_correct / reward)
    - Total turns

Unit of analysis:
  - Paired per question (BASE vs RL)
  - Per trajectory (for means and quartiles)

Uncertainty:
  - 5k bootstrap resamples clustered by question

Primary plots:
  A1: Cohort means (bars + 95% CIs) for RQI, Turns, Refined%, Repeat%, Success
  Reasoning type grounded ratios: Grounded ratios by reasoning type for each model

Sensitivity toggles:
  - --require_clear_for_sufficient (default: True) to compute Turns-to-First-Sufficient as Sufficient&Clear
  - --exclude_pre_sufficient_answers (default: False) to drop trajectories that answered before any sufficient evidence
  

Usage:
  python grounded_reason.py \
    --input final_annotated_traces.jsonl \
    --outdir figs_cohort \
    --require_clear_for_sufficient \
    --exclude_pre_sufficient_answers
"""

import os
import json
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict, Counter
import hashlib


sns.set_theme(context='paper', style='whitegrid', palette='colorblind', font_scale=1.05)
plt.rcParams.update({
    'figure.dpi': 180,
    'savefig.dpi': 300,
    'axes.titlesize': 12,
    'axes.labelsize': 10,
    'legend.fontsize': 9,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
})

QUERY_TYPES_ALL = {'RefinedQuery', 'FollowUpQuery', 'RepeatQuery', 'NewQuery', 'InitialQuery', 'Query'}
QUERY_TYPES_REFINED = {'RefinedQuery'}
QUERY_TYPES_FOLLOWUP = {'FollowUpQuery'}
QUERY_TYPES_REPEAT = {'RepeatQuery'}

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)

def savefig(fig, outdir, name):
    ensure_dir(outdir)
    p1 = os.path.join(outdir, f'{name}.png')
    fig.savefig(p1, bbox_inches='tight')
    print(f"Saved {p1}")
    plt.close(fig)

# Global model color palette (shared across figures)
MODEL_COLOR_PALETTE = {
    'Qwen3-30B-A3B-Instruct-2507': '#460057',          
    'Qwen3-30B-A3B': '#1abc9c',
      
}

def get_model_color(model_name: str) -> str:
    return MODEL_COLOR_PALETTE.get(model_name, '#7f7f7f')

def clean_and_categorize_model(model_name: str):
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
    # Legacy models
    if "Qwen3-30B-A3B-Instruct-2507" in model_name in model_name:
        return "Qwen3-30B-A3B-Instruct-2507", "Base" 
    if "Qwen3-30B-A3B" in model_name  in model_name:
        return "Qwen3-30B-A3B", "Base"
    if "fewshot-Qwen2.5-7B-Instruct" in model_name:
        return "Few-shot (Qwen)", "Few-shot"
    if "cot-Qwen2.5-7B-Instruct" in model_name:
        return "CoT (Qwen)", "CoT (Qwen)"
    if "react-Qwen2.5-7B-Instruct" in model_name:
        return "ReAct (Qwen)", "ReAct (Qwen)"
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

def get_model_order():
    return ["Qwen3-30B-A3B-Instruct-2507 (Qwen)", "Qwen3-30B-A3B'(Qwen)"]


def load_traces(path: str):
    rows = []
    with open(path, 'r') as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise e
    return rows

def prefer_success_flag(t: dict) -> int:
    if 'is_correct' in t:
        return int(bool(t.get('is_correct')))
    if 'reward' in t:
        return int(bool(t.get('reward')))
    # fallback: presence of CorrectAnswer step
    for s in (t.get('trace') or []):
        ann = s.get('annotation', {})
        if isinstance(ann, dict) and ann.get('type') == 'CorrectAnswer':
            return 1
    return 0

def compute_rqi(trace_steps: list, category: str = None) -> float:
    """Compute RQI: fraction of reasoning steps with groundness=Grounded AND anchor_type=EVIDENCE.
    Includes InformationSynthesis, PlanFormation, and StateAssessment steps.
    For 'DeepResearch' category, also includes 'search' steps.
    """
    num_reasoning = 0
    num_reasoning_grounded = 0
    for step in trace_steps:
        ann = step.get('annotation', {})
        if not isinstance(ann, dict): 
            continue
        
        reasoning_type = ann.get('type', 'Unknown')
        is_reasoning_step = False
        if reasoning_type in ["InformationSynthesis", "PlanFormation", "StateAssessment"]:
            is_reasoning_step = True
        elif category == 'DeepResearch' and step.get('type') == 'search':
            is_reasoning_step = True

        if not is_reasoning_step:
            continue

        # Count all eligible reasoning steps
        
        attrs = ann.get('attributes', {}) or {}
        g = str(attrs.get('groundness', '')).lower()
        anchor = str(attrs.get('anchor_type', '')).upper()
        if anchor == 'EVIDENCE':
            num_reasoning += 1
            if g == 'grounded':
                num_reasoning_grounded += 1
    if num_reasoning == 0:
        return np.nan
    return num_reasoning_grounded / num_reasoning

def compute_rqi_by_reasoning_type(trace_steps: list, category: str = None) -> dict:
    """Compute grounded ratio by reasoning type. Grounded requires anchor_type=EVIDENCE.
    For 'DeepResearch' category, 'search' steps are mapped to 'PlanFormation'.
    Returns dict: {reasoning_type: (total_count, grounded_count, grounded_ratio)}
    """
    reasoning_stats = defaultdict(lambda: {'total': 0, 'grounded': 0})
    
    for step in trace_steps:
        ann = step.get('annotation', {})
        if not isinstance(ann, dict): 
            continue
        attrs = ann.get('attributes', {}) or {}

        reasoning_type = ann.get('type', 'Unknown')
        is_reasoning_step = False
        if reasoning_type in ["InformationSynthesis", "PlanFormation", "StateAssessment"]:
            is_reasoning_step = True
        elif category == 'DeepResearch' and step.get('type') == 'search':
            is_reasoning_step = True
            reasoning_type = "PlanFormation"  # Map search to PlanFormation for these models

        if not is_reasoning_step:
            continue

        g = str(attrs.get('groundness', '')).lower()
        anchor = str(attrs.get('anchor_type', '')).upper()
        if anchor == 'EVIDENCE':
            reasoning_stats[reasoning_type]['total'] += 1
            if g == 'grounded':
                reasoning_stats[reasoning_type]['grounded'] += 1
    
    # Convert to final format with ratios
    result = {}
    for reasoning_type, stats in reasoning_stats.items():
        total = stats['total']
        grounded = stats['grounded']
        ratio = grounded / total if total > 0 else np.nan
        result[reasoning_type] = {
            'total_count': total,
            'grounded_count': grounded,
            'grounded_ratio': ratio
        }
    
    return result

def compute_turns_to_first_sufficient(trace_steps: list, require_clear: bool = True) -> float:
    # Count turns until first search_result with Sufficient (& Clear if required).
    for idx, step in enumerate(trace_steps):
        ann = step.get('annotation', {})
        if not isinstance(ann, dict):
            continue
        if ann.get('type') == 'search_result':
            attrs = (ann.get('attributes', {}) or {})
            iq = attrs.get('information_quality')
            ic = attrs.get('information_clarity')
            if iq == 'Sufficient' and ((not require_clear) or (ic == 'Clear')):
                return idx  # number of steps before this event
    return np.nan

def compute_query_action_mix_and_rates(trace_steps: list):
    total_query = 0
    cnt_initial = 0
    cnt_refine = 0
    cnt_follow = 0
    cnt_repeat = 0
    for step in trace_steps:
        ann = step.get('annotation', {})
        if not isinstance(ann, dict):
            continue
        tpe = ann.get('type')
        if tpe in QUERY_TYPES_ALL:
            total_query += 1
            if tpe in QUERY_TYPES_REFINED:
                cnt_refine += 1
            elif tpe in QUERY_TYPES_FOLLOWUP:
                cnt_follow += 1
            elif tpe in QUERY_TYPES_REPEAT:
                cnt_repeat += 1
            else:
                cnt_initial += 1
    rates = {
        'refined_rate': (cnt_refine / total_query) if total_query > 0 else np.nan,
        'repeat_rate': (cnt_repeat / total_query) if total_query > 0 else np.nan,
    }
    mix = {
        'Initial': cnt_initial,
        'Refined': cnt_refine,
        'Follow-up': cnt_follow,
        'Repeat': cnt_repeat,
        'total_query': total_query
    }
    return rates, mix

def answered_before_any_sufficient(trace_steps: list, require_clear: bool = True) -> bool:
    saw_correct = False
    saw_sufficient = False
    for step in trace_steps:
        ann = step.get('annotation', {})
        if not isinstance(ann, dict):
            continue
        tpe = ann.get('type')
        if tpe == 'search_result':
            attrs = (ann.get('attributes', {}) or {})
            iq = attrs.get('information_quality')
            ic = attrs.get('information_clarity')
            if iq == 'Sufficient' and ((not require_clear) or (ic == 'Clear')):
                saw_sufficient = True
        if tpe == 'CorrectAnswer':
            saw_correct = True
        if saw_correct and (not saw_sufficient):
            return True
    return False

def build_trajectory_df(traces: list, require_clear_sufficient: bool, exclude_pre_suff_answers: bool):
    rows = []
    for t in traces:
        model_clean, cat = clean_and_categorize_model(t.get('model', ''))
        if cat == 'Other':
            continue
        dataset = t.get('dataset', 'Unknown')
        qid = t.get('question_id', t.get('id', None))
        if qid is None:
            # Deterministic hash using dataset + question text (avoid free-text IDs)
            q_text = str(t.get('question', ''))
            qid = hashlib.sha1(f"{dataset}||{q_text}".encode('utf-8')).hexdigest()[:16]
        steps = t.get('trace', []) or []
        if exclude_pre_suff_answers and answered_before_any_sufficient(steps, require_clear=require_clear_sufficient):
            continue
        rqi = compute_rqi(steps, cat)
        rqi_by_type = compute_rqi_by_reasoning_type(steps, cat)
        turns_to_suff = compute_turns_to_first_sufficient(steps, require_clear=require_clear_sufficient)
        rates, mix = compute_query_action_mix_and_rates(steps)
        success = prefer_success_flag(t)
        total_turns = len(steps)
        rows.append({
            'model_raw': t.get('model', ''),
            'model': model_clean,
            'category': cat,
            'dataset': dataset,
            'question_id': qid,
            'rqi': rqi,
            'rqi_by_type': rqi_by_type,  # Store reasoning type statistics
            'turns_to_first_sufficient': turns_to_suff,
            'refined_rate': rates['refined_rate'],
            'repeat_rate': rates['repeat_rate'],
            'success': success,
            'total_turns': total_turns,
            'mix_initial': mix['Initial'],
            'mix_refined': mix['Refined'],
            'mix_follow': mix['Follow-up'],
            'mix_repeat': mix['Repeat'],
            'mix_total_query': mix['total_query'],
        })
    df = pd.DataFrame(rows)
    return df

"""Pairing/filtering removed: all models are evaluated on their full coverage."""


def cluster_bootstrap_ci_by_model(df_paired_all: pd.DataFrame, metric: str, n_boot: int = 2000, seed: int = 42):
    """Compute per-model mean and bootstrap CI clustered by question pairs.
    df_paired_all should contain only trajectories for the paired (dataset,question) set.
    Returns a dict: model -> (mean, lo, hi)
    """
    rng = np.random.default_rng(seed)
    pairs = sorted(set(zip(df_paired_all['dataset'], df_paired_all['question_id'])))
    if len(pairs) == 0:
        return {}
    models = sorted(df_paired_all['model'].unique())
    # precompute model -> array aligned to pairs
    model_arrays = {}
    gb = df_paired_all.groupby(['model','dataset','question_id'])[metric].mean()
    for m in models:
        arr = np.full(len(pairs), np.nan, dtype=float)
        for i, (d, q) in enumerate(pairs):
            try:
                arr[i] = float(gb.loc[(m, d, q)])
            except Exception:
                arr[i] = np.nan
        model_arrays[m] = arr

    results = {}
    n = len(pairs)
    if n == 0:
        return results
    idx_cache = rng.integers(0, n, size=(n_boot, n))
    for m, arr in model_arrays.items():
        if np.all(np.isnan(arr)):
            results[m] = (np.nan, np.nan, np.nan)
            continue
        point = float(np.nanmean(arr))
        samp = np.empty(n_boot, dtype=float)
        for i in range(n_boot):
            sel = idx_cache[i]
            samp[i] = float(np.nanmean(arr[sel]))
        lo, hi = float(np.nanpercentile(samp, 2.5)), float(np.nanpercentile(samp, 97.5))
        results[m] = (point, lo, hi)
    return results

# Paired bootstrap and deltas removed

def compute_action_mix(df: pd.DataFrame):
    # Sum counts across trajectories, compute percentages
    tot = df['mix_total_query'].sum()
    if tot == 0:
        return {'Initial': 0, 'Refined': 0, 'Follow-up': 0, 'Repeat': 0}
    return {
        'Initial': float(df['mix_initial'].sum() / tot * 100.0),
        'Refined': float(df['mix_refined'].sum() / tot * 100.0),
        'Follow-up': float(df['mix_follow'].sum() / tot * 100.0),
        'Repeat': float(df['mix_repeat'].sum() / tot * 100.0),
    }

def aggregate_rqi_by_reasoning_type(df: pd.DataFrame) -> dict:
    """Aggregate reasoning type statistics across all trajectories in df.
    Returns dict: {reasoning_type: {'total_count': int, 'grounded_count': int, 'grounded_ratio': float}}
    """
    aggregated = defaultdict(lambda: {'total_count': 0, 'grounded_count': 0})
    
    for _, row in df.iterrows():
        rqi_by_type = row.get('rqi_by_type', {})
        if not isinstance(rqi_by_type, dict):
            continue
            
        for reasoning_type, stats in rqi_by_type.items():
            if isinstance(stats, dict):
                aggregated[reasoning_type]['total_count'] += stats.get('total_count', 0)
                aggregated[reasoning_type]['grounded_count'] += stats.get('grounded_count', 0)
    
    # Compute ratios
    result = {}
    for reasoning_type, stats in aggregated.items():
        total = stats['total_count']
        grounded = stats['grounded_count']
        ratio = grounded / total if total > 0 else np.nan
        result[reasoning_type] = {
            'total_count': total,
            'grounded_count': grounded,
            'grounded_ratio': ratio
        }
    
    return result

# ---------------------------
# Standardization helpers
# ---------------------------

def compute_reference_type_weights(df: pd.DataFrame) -> dict:
    """Reference type distribution pooled over models; keys are reasoning types."""
    stats = aggregate_rqi_by_reasoning_type(df)
    # aggregate again over all models already done at df-level; but we need totals across df
    # If df includes multiple models, aggregate_rqi_by_reasoning_type already sums across rows
    totals = {rt: s['total_count'] for rt, s in stats.items()}
    total = sum(totals.values()) or 1
    return {rt: (cnt/total) for rt, cnt in totals.items()}

def compute_reference_E_weights(step_df: pd.DataFrame) -> dict:
    """Reference E distribution pooled over models using step counts."""
    if step_df is None or step_df.empty:
        return {0: 0.0, 1: 0.0, 2: 0.0}
    counts = step_df['E'].value_counts().to_dict()
    total = sum(counts.values()) or 1
    return {k: counts.get(k, 0)/total for k in [0,1,2]}

def clustered_standardized_over_E(sub_steps: pd.DataFrame, E_weights: dict, n_boot: int = 2000, seed: int = 42):
    """Compute standardized P(grounded) = Σ_k w_k * P(grounded|E=k) with cluster bootstrap.
    Returns (point, lo, hi).
    Clusters are (dataset, question_id).
    """
    if sub_steps is None or sub_steps.empty:
        return (np.nan, np.nan, np.nan)
    sub = sub_steps.copy()
    sub['cluster'] = list(zip(sub['dataset'], sub['question_id']))
    clusters = sorted(sub['cluster'].unique())
    if not clusters:
        return (np.nan, np.nan, np.nan)
    # Precompute numer/denom arrays per E level
    E_levels = [0,1,2]
    numer = {k: np.zeros(len(clusters), dtype=float) for k in E_levels}
    denom = {k: np.zeros(len(clusters), dtype=float) for k in E_levels}
    cluster_to_idx = {c:i for i,c in enumerate(clusters)}
    for _, r in sub.iterrows():
        i = cluster_to_idx[r['cluster']]
        k = int(r['E']) if r['E'] in E_levels else None
        if k is None:
            continue
        denom[k][i] += 1.0
        numer[k][i] += float(r.get('grounded_flag', 0))
    # Point estimate
    p_k = {}
    for k in E_levels:
        den = denom[k].sum()
        p_k[k] = (numer[k].sum()/den) if den>0 else np.nan
    point = float(np.nansum([E_weights.get(k,0.0)*p_k.get(k,np.nan) for k in E_levels]))
    # Bootstrap
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(clusters), size=(n_boot, len(clusters)))
    samp = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        sel = idx[b]
        total = 0.0
        for k in E_levels:
            n_sel = float(numer[k][sel].sum())
            d_sel = float(denom[k][sel].sum())
            pk = (n_sel/d_sel) if d_sel>0 else np.nan
            if np.isnan(pk):
                continue
            total += E_weights.get(k, 0.0) * pk
        samp[b] = total
    lo, hi = float(np.nanpercentile(samp, 2.5)), float(np.nanpercentile(samp, 97.5))
    return point, lo, hi


# ---------------------------
# RQI-E: Evidence-level reasoning propensity utilities
# ---------------------------

def map_evidence_level(iq: str, ic: str) -> int:
    """Map information_quality, information_clarity to E∈{0,1,2}.
    Defaults: non-'Sufficient' -> E=0. Missing clarity counts as Unclear.
    """
    iq = (iq or '').strip()
    ic = (ic or '').strip()
    if iq == 'Sufficient':
        if ic == 'Clear':
            return 2
        else:
            return 1
    return 0


def build_reasoning_step_df(traces: list) -> pd.DataFrame:
    """Build per-reasoning-step records with cumulative evidence level E at each step.
    Fields per row: model, category, dataset, question_id, step_index, E, grounded_flag, reasoning_type
    
    NOTE: For this specific evidence-centric analysis, 'grounded_flag' is set to 1 only if
    `groundness` is 'grounded' AND `anchor_type` is 'EVIDENCE'. This provides a
    stricter measure of how well the model's reasoning is tied to retrieved evidence.
    """
    rows = []
    for t in traces:
        model_clean, cat = clean_and_categorize_model(t.get('model', ''))
        if cat == 'Other':
            continue
        dataset = t.get('dataset', 'Unknown')
        qid = t.get('question_id', t.get('id', None))
        if qid is None:
            q_text = str(t.get('question', ''))
            qid = hashlib.sha1(f"{dataset}||{q_text}".encode('utf-8')).hexdigest()[:16]
        steps = t.get('trace', []) or []
        cur_E = 0
        for i, step in enumerate(steps):
            ann = step.get('annotation', {})
            if isinstance(ann, dict) and ann.get('type') == 'search_result':
                attrs = (ann.get('attributes', {}) or {})
                cur_E = max(cur_E, map_evidence_level(attrs.get('information_quality'), attrs.get('information_clarity')))
                # continue to next step; reasoning step may also occur at same index in other data, so do not skip
            # Select reasoning steps
            if not isinstance(ann, dict):
                continue
            reasoning_type = ann.get('type', 'Unknown')
            if reasoning_type not in ["InformationSynthesis", "PlanFormation", "StateAssessment"]:
                continue
            attrs = (ann.get('attributes', {}) or {})
            grounding = str(attrs.get('groundness', '')).lower()
            anchor = str(attrs.get('anchor_type', '')).upper()
            # For RQI-E analysis, "Grounded" strictly means grounded in EVIDENCE.
            grounded_flag = 1 if (grounding == "grounded" and anchor == "EVIDENCE") else 0
            rows.append({
                'model': model_clean,
                'category': cat,
                'dataset': dataset,
                'question_id': qid,
                'step_index': i,
                'E': int(cur_E),
                'grounded_flag': grounded_flag,
                'reasoning_type': reasoning_type,
            })
    return pd.DataFrame(rows)


def clustered_ratio_ci(numer_by_cluster: dict, denom_by_cluster: dict, n_boot: int = 2000, seed: int = 42):
    """Bootstrap CI for a ratio of sums across clusters.
    numer_by_cluster, denom_by_cluster: dict cluster_id -> float. Returns (point, lo, hi).
    """
    rng = np.random.default_rng(seed)
    clusters = list(denom_by_cluster.keys())
    if not clusters:
        return (np.nan, np.nan, np.nan)
    numer = np.array([float(numer_by_cluster.get(c, 0.0)) for c in clusters])
    denom = np.array([float(denom_by_cluster.get(c, 0.0)) for c in clusters])
    num_sum = float(numer.sum())
    den_sum = float(denom.sum())
    point = (num_sum / den_sum) if den_sum > 0 else np.nan
    n = len(clusters)
    idx = rng.integers(0, n, size=(n_boot, n))
    samp = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        sel = idx[i]
        num_b = float(numer[sel].sum())
        den_b = float(denom[sel].sum())
        samp[i] = (num_b / den_b) if den_b > 0 else np.nan
    lo, hi = float(np.nanpercentile(samp, 2.5)), float(np.nanpercentile(samp, 97.5))
    return point, lo, hi


def plot_RQI_E_A_propensity(step_df: pd.DataFrame, outdir: str, n_boot: int = 2000):
    """Fig RQI-E A: P(grounded | E=k) with 95% CI by model (all models)."""
    if step_df.empty:
        fig, ax = plt.subplots(figsize=(8, 4)); ax.set_title('RQI-E A (no data)'); ax.axis('off'); savefig(fig, outdir, 'fig_RQI_E_A_propensity'); return
    
    models_present = list(step_df['model'].dropna().unique())
    models_order = [m for m in get_model_order() if m in models_present]
    E_levels = [0, 1, 2]
    x = np.array(E_levels)

    fig, ax = plt.subplots(1, 1, figsize=(8, 4))

    for i, m in enumerate(models_order):
        sub = step_df[step_df['model'] == m].copy()
        if sub.empty:
            continue
        sub['cluster'] = list(zip(sub['dataset'], sub['question_id']))
        pts, los, his = [], [], []
        for k in E_levels:
            k_df = sub[sub['E'] == k]
            numer = defaultdict(float); denom = defaultdict(float)
            for _, r in k_df.iterrows():
                c = r['cluster']; denom[c] += 1.0; numer[c] += float(r['grounded_flag'])
            p, lo, hi = clustered_ratio_ci(numer, denom, n_boot=n_boot)
            pts.append(p); los.append(lo); his.append(hi)
        pts = np.array(pts)
        yerr = np.vstack([pts - np.array(los), np.array(his) - pts])
        
        # Emphasize Base and Few-shot lines
        linewidth = 3 if m in ['Base (Qwen)', 'Few-shot (Qwen)'] else 1.5
        ax.errorbar(x, pts, yerr=yerr, fmt='o-', capsize=3, color=get_model_color(m), 
                   label=m, linewidth=linewidth, markersize=6)
    
    ax.set_title('P(grounded | E) by model')
    ax.set_xticks(x); ax.set_xticklabels([f'E={k}' for k in E_levels])
    ax.set_ylabel('P(grounded | E)'); ax.set_ylim(0, 0.7)
    ax.legend(fontsize=8, bbox_to_anchor=(1.02, 1), loc='upper left')
    ax.grid(axis='y', alpha=0.3)

    fig.suptitle('RQI-E A: Evidence-conditioned grounding propensity (95% CI)')
    plt.tight_layout()
    savefig(fig, outdir, 'fig_RQI_E_A_propensity')

    # New: E-standardized overall P(grounded) per model (direct standardization)
    print('\nE-standardized P(grounded) per model (pooled E distribution):')
    E_ref = compute_reference_E_weights(step_df)
    for m in models_order:
        sub = step_df[step_df['model'] == m]
        p, lo, hi = clustered_standardized_over_E(sub, E_ref, n_boot=n_boot)
        print(f"{m:25s} {('NA' if np.isnan(p) else f'{p:5.3f}')} [{('NA' if np.isnan(lo) else f'{lo:5.3f}')}, {('NA' if np.isnan(hi) else f'{hi:5.3f}')}]")


def plot_RQI_E_B_by_type(step_df: pd.DataFrame, outdir: str, n_boot: int = 2000):
    """Fig RQI-E B: P(grounded | E=k) split by reasoning type, with lines per model (all models)."""
    if step_df.empty:
        fig, ax = plt.subplots(figsize=(8, 4)); ax.set_title('RQI-E B (no data)'); ax.axis('off'); savefig(fig, outdir, 'fig_RQI_E_B_by_type'); return
    reasoning_types = ["InformationSynthesis", "PlanFormation", "StateAssessment"]
    models_present = list(step_df['model'].dropna().unique())
    models_order = [m for m in get_model_order() if m in models_present]
    E_levels = [0, 1, 2]
    x = np.array(E_levels)
    fig, axes = plt.subplots(1, len(reasoning_types), figsize=(max(12, 5*len(reasoning_types)), 4), sharey=True)
    if len(reasoning_types) == 1:
        axes = [axes]
    for ax_idx, rt in enumerate(reasoning_types):
        ax = axes[ax_idx]
        sub_rt = step_df[step_df['reasoning_type'] == rt].copy()
        if sub_rt.empty:
            ax.set_axis_off(); continue
        for m in models_order:
            sub = sub_rt[sub_rt['model'] == m].copy()
            if sub.empty:
                continue
            sub['cluster'] = list(zip(sub['dataset'], sub['question_id']))
            pts, los, his = [], [], []
            for k in E_levels:
                k_df = sub[sub['E'] == k]
                numer = defaultdict(float); denom = defaultdict(float)
                for _, r in k_df.iterrows():
                    c = r['cluster']; denom[c] += 1.0; numer[c] += float(r['grounded_flag'])
                p, lo, hi = clustered_ratio_ci(numer, denom, n_boot=n_boot)
                pts.append(p); los.append(lo); his.append(hi)
            pts = np.array(pts)
            yerr = np.vstack([pts - np.array(los), np.array(his) - pts])
            linewidth = 3 if m in ['Base (Qwen)', 'Few-shot (Qwen)'] else 1.5
            label = m if ax_idx == 0 else '_nolegend_'
            ax.errorbar(x, pts, yerr=yerr, fmt='o-', capsize=3, color=get_model_color(m),
                        label=label, linewidth=linewidth, markersize=5)
        ax.set_title(rt)
        ax.set_xticks(x); ax.set_xticklabels([f'E={k}' for k in E_levels])
        if ax_idx == 0:
            ax.set_ylabel('P(grounded | E)')
        ax.set_ylim(0, 1)
        ax.grid(axis='y', alpha=0.3)
    axes[0].legend(fontsize=8, bbox_to_anchor=(1.02, 1), loc='upper left')
    fig.suptitle('RQI-E B: Grounding propensity by reasoning type and evidence level (per model)')
    plt.tight_layout()
    savefig(fig, outdir, 'fig_RQI_E_B_by_type')


def plot_RQI_E_A_enhanced_bar(step_df: pd.DataFrame, outdir: str, n_boot: int = 2000):
    """Enhanced Fig RQI-E A: Bar chart of P(grounded | E) for all models.
    X axis: E in {0,1,2}. Bars: models. Y: P(grounded|E) with 95% CI.
    """
    if step_df.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.set_title('RQI-E A Enhanced (no data)')
        ax.axis('off')
        savefig(fig, outdir, 'fig_RQI_E_A_enhanced')
        return

    models_present = list(step_df['model'].dropna().unique())
    models_order = [m for m in get_model_order() if m in models_present]
    E_levels = [0, 1, 2]
    x = np.arange(len(E_levels))
    width = 0.8 / max(1, len(models_order))

    fig, ax = plt.subplots(1, 1, figsize=(10, 5))

    for i, m in enumerate(models_order):
        sub = step_df[step_df['model'] == m].copy()
        if sub.empty:
            continue
        sub['cluster'] = list(zip(sub['dataset'], sub['question_id']))
        pts, los, his = [], [], []
        for k in E_levels:
            k_df = sub[sub['E'] == k]
            numer = defaultdict(float); denom = defaultdict(float)
            for _, r in k_df.iterrows():
                c = r['cluster']; denom[c] += 1.0; numer[c] += float(r['grounded_flag'])
            p, lo, hi = clustered_ratio_ci(numer, denom, n_boot=n_boot)
            pts.append(p); los.append(lo); his.append(hi)
        pts = np.array(pts)
        los = np.clip(np.array(los), 0.0, 1.0)
        his = np.clip(np.array(his), 0.0, 1.0)
        yerr = np.vstack([pts - los, his - pts])
        ax.bar(x + i * width, np.nan_to_num(pts, nan=0.0), width=width*0.95, color=get_model_color(m), label=m, alpha=0.9)
        ax.errorbar(x + i * width, pts, yerr=yerr, fmt='none', ecolor='black', capsize=3)
        # numeric labels
        for j, v in enumerate(pts):
            if np.isnan(v):
                continue
            ax.text(x[j] + i * width, v + 0.07, f"{v:.2f}", ha='center', va='bottom', fontsize=8, rotation=45, 
            bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.75, edgecolor='none'))

    ax.set_xticks(x + width * (len(models_order) - 1) / 2)
    ax.set_xticklabels([f'E={k}' for k in E_levels])
    ax.set_ylabel('P(grounded | E)')
    ax.set_title('RQI-E A (Enhanced): Evidence-conditioned grounding (bars, 95% CI)')
    ax.set_ylim(0, 1)
    ax.grid(axis='y', alpha=0.3)
    ax.legend(title='Model', bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=8)

    plt.tight_layout()
    savefig(fig, outdir, 'fig_RQI_E_A_enhanced')

def plot_RQI_E_B_enhanced_by_type(step_df: pd.DataFrame, outdir: str, n_boot: int = 2000):
    """Enhanced Fig RQI-E B: Three subplots (E=0,1,2). X: reasoning types.
    Grouped bars per model with 95% CI, wider bars and clearer labels.
    """
    if step_df.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.set_title('RQI-E B Enhanced (no data)')
        ax.axis('off')
        savefig(fig, outdir, 'fig_RQI_E_B_enhanced')
        return

    reasoning_types = ["InformationSynthesis", "PlanFormation", "StateAssessment"]
    # Shorter display labels for readability
    rt_display = ["Info. Synth.", "Plan Form.", "State Assess."]
    models_present = list(step_df['model'].dropna().unique())
    models_order = [m for m in get_model_order() if m in models_present]
    E_levels = [0, 1, 2]

    # Increase figure width for wider subfigures
    fig, axes = plt.subplots(1, len(E_levels), figsize=(max(24, 8*len(E_levels)), 5), sharey=True)
    if not isinstance(axes, (list, np.ndarray)):
        axes = [axes]

    x = np.arange(len(reasoning_types))
    width = min(0.5, 0.95 / max(1, len(models_order)))  # Wider bars
    
    # Create legend at the top of the figure
    legend_elements = [plt.Rectangle((0,0), 1, 1, color=get_model_color(m), label=m) 
                      for m in models_order]
    fig.legend(handles=legend_elements, loc='upper center', ncol=len(models_order), 
              fontsize=10, title='Model', title_fontsize=11, bbox_to_anchor=(0.5, 1.1))
    
    # Add padding at the top for the legend
    plt.subplots_adjust(top=0.85)

    for ax_idx, k in enumerate(E_levels):
        ax = axes[ax_idx]
        sub_k = step_df[step_df['E'] == k].copy()
        if sub_k.empty:
            ax.set_axis_off(); continue
        sub_k['cluster'] = list(zip(sub_k['dataset'], sub_k['question_id']))

        for i, m in enumerate(models_order):
            sub_m = sub_k[sub_k['model'] == m]
            if sub_m.empty:
                continue
            pts, los, his = [], [], []
            for rt in reasoning_types:
                krt_df = sub_m[sub_m['reasoning_type'] == rt]
                numer = defaultdict(float); denom = defaultdict(float)
                for _, r in krt_df.iterrows():
                    c = r['cluster']; denom[c] += 1.0; numer[c] += float(r['grounded_flag'])
                p, lo, hi = clustered_ratio_ci(numer, denom, n_boot=n_boot)
                pts.append(p); los.append(lo); his.append(hi)
            pts = np.array(pts)
            los = np.clip(np.array(los), 0.0, 1.0)
            his = np.clip(np.array(his), 0.0, 1.0)
            yerr = np.vstack([pts - los, his - pts])

            # Center groups around x by offsetting
            offsets = (i - (len(models_order) - 1) / 2) * width
            ax.bar(x + offsets, np.nan_to_num(pts, nan=0.0), width=width*1.0,
                   color=get_model_color(m), edgecolor='white', linewidth=0.6,
                   label=(m if ax_idx == 0 else '_nolegend_'), alpha=0.95)
            ax.errorbar(x + offsets, pts, yerr=yerr, fmt='none', ecolor='black', capsize=3)

            # numeric labels above bars
            for j, v in enumerate(pts):
                if np.isnan(v):
                    continue
                ax.text(x[j] + offsets, v + 0.05, f"{v:.2f}", ha='center', va='bottom', fontsize=10, rotation=45,
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.75, edgecolor='none'))

        ax.set_title(f'E={k}', fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(rt_display, rotation=0, ha='center')
        ax.tick_params(axis='x', labelsize=11)
        ax.tick_params(axis='y', labelsize=11)
        if ax_idx == 0:
            ax.set_ylabel('P(grounded | E, type)')
        ax.set_ylim(0, 1.12)
        ax.grid(axis='y', alpha=0.3)

    # axes[0].legend(title='Model', bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=9, title_fontsize=10)
    fig.suptitle('RQI-E B (Enhanced): Evidence-conditioned grounding by reasoning type (bars, 95% CI)')
    plt.tight_layout()
    savefig(fig, outdir, 'fig_RQI_E_B_enhanced')


def plot_A1_means(df_paired_all, outdir, n_boot=2000):
    """Plot per-model cohort means (no grouping BASE vs RL) for the five metrics."""
    metrics = [
        ('rqi', 'RQI (fraction grounded)'),
        ('turns_to_first_sufficient', 'Turns to First Sufficient (lower=better)'),
        ('refined_rate', 'RefinedQuery Rate (%)'),
        ('repeat_rate', 'RepeatQuery Rate (%)'),
        ('success', 'Success Rate (%)'),
    ]
    # Use consistent model ordering
    available_models = df_paired_all['model'].unique()
    model_order = get_model_order()
    models = [m for m in model_order if m in available_models]

    # Use all available data per model (unpaired, no intersection filtering)
    df_used = df_paired_all
    fig, axes = plt.subplots(2, 3, figsize=(14,8)); ax_list = axes.flatten()
    for idx, (metric, title) in enumerate(metrics):
        ax = ax_list[idx]
        scale = 100.0 if metric in {'refined_rate','repeat_rate','success'} else 1.0
        res = cluster_bootstrap_ci_by_model(df_used, metric, n_boot=n_boot)
        means = [res.get(m, (np.nan, np.nan, np.nan))[0]*scale for m in models]
        lo = [res.get(m, (np.nan, np.nan, np.nan))[1]*scale for m in models]
        hi = [res.get(m, (np.nan, np.nan, np.nan))[2]*scale for m in models]
        x = np.arange(len(models))
        ax.bar(x, means, color=[get_model_color(m) for m in models])
        yerr = np.vstack([np.array(means)-np.array(lo), np.array(hi)-np.array(means)])
        ax.errorbar(x, means, yerr=yerr, fmt='none', ecolor='black', capsize=3)
        ax.set_xticks(x); ax.set_xticklabels(models, rotation=45, ha='right')
        ax.set_title(title); ax.grid(axis='y', alpha=0.3)
        for xi, v in zip(x, means):
            if not np.isnan(v):
                ax.text(xi, v + 0.05, f"{v:.2f}", ha='center', va='bottom', fontsize=8)
    ax_list[-1].axis('off')
    plt.tight_layout()
    savefig(fig, outdir, 'fig_A1_means_per_model')






def plot_reasoning_type_grounded_ratios(df_paired_all, outdir):
    """Plot grounded ratios by reasoning type for each model."""
    # Use all available data (unpaired)
    df_used = df_paired_all

    # Use consistent model ordering
    available_models = df_used['model'].unique()
    model_order = get_model_order()
    models = [m for m in model_order if m in available_models]
    
    # Collect data for all models and reasoning types
    all_reasoning_types = set()
    model_data = {}
    
    for model in models:
        sub_df = df_used[df_used['model'] == model]
        reasoning_stats = aggregate_rqi_by_reasoning_type(sub_df)
        model_data[model] = reasoning_stats
        
        # Collect all reasoning types
        all_reasoning_types.update(reasoning_stats.keys())
    
    if not all_reasoning_types:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.set_title('Reasoning Type Grounded Ratios (no data)')
        ax.axis('off')
        savefig(fig, outdir, 'fig_reasoning_type_grounded_ratios')
        return
    
    # Sort reasoning types for consistent ordering
    reasoning_types = sorted(all_reasoning_types)
    
    # Create the plot
    fig, ax = plt.subplots(figsize=(max(12, len(reasoning_types) * 1.5), 6))
    
    # Prepare data for plotting
    x = np.arange(len(reasoning_types))
    width = 0.8 / len(models)  # Width of bars
    
    for i, model in enumerate(models):
        ratios = []
        counts = []
        for rt in reasoning_types:
            stats = model_data[model].get(rt, {})
            ratio = stats.get('grounded_ratio', np.nan)
            total_count = stats.get('total_count', 0)
            ratios.append(ratio if not np.isnan(ratio) else 0)
            counts.append(total_count)
        
        # Plot bars
        bars = ax.bar(x + i * width, ratios, width,
                     label=model, color=get_model_color(model))
        
        # Add count annotations on bars
        for j, (bar, count) in enumerate(zip(bars, counts)):
            if count > 0:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                       f'{ratios[j]:.2f}', ha='center', va='bottom', fontsize=8)
    ax.set_xlabel('Reasoning Type')
    ax.set_ylabel('Grounded Ratio')
    ax.set_title('Grounded Ratios by Reasoning Type (per model)')
    ax.set_xticks(x + width * (len(models) - 1) / 2)
    ax.set_xticklabels(reasoning_types, rotation=45, ha='right')
    ax.legend(title='Model', bbox_to_anchor=(1.02, 1), loc='upper left')
    ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(0, 1.1)
    
    plt.tight_layout()
    savefig(fig, outdir, 'fig_reasoning_type_grounded_ratios')

    # Also compute and print type-standardized and macro-average RQI with pooled weights
    ref_w = compute_reference_type_weights(df_used)
    type_list = sorted(ref_w.keys())
    print('\nType standardization (pooled weights) — grounded ratio:')
    print(f"{'Model':40s} {'MacroAvg':>8s} {'Std(w_ref)':>10s}")
    for m in models:
        stats = model_data[m]
        rates = {t: stats.get(t, {}).get('grounded_ratio', np.nan) for t in type_list}
        valid = [r for r in rates.values() if not np.isnan(r)]
        macro = np.mean(valid) if valid else np.nan
        std = float(np.nansum([ref_w.get(t,0.0)*rates.get(t,np.nan) for t in type_list]))
        print(f"{m:40s} {(f'{macro:6.3f}' if not np.isnan(macro) else '  NA  '):>8s} {(f'{std:8.3f}' if not np.isnan(std) else '    NA   '):>10s}")


def print_summary_results(df_all: pd.DataFrame, outdir: str, n_boot: int = 2000):
    """Print per-model summaries with bootstrap CIs and action mix (no pairing)."""
    print('\n' + '='*72)
    print('SUMMARY (per model) — unpaired across all questions (as available)')
    print('='*72)
    # Use consistent model ordering
    available_models = df_all['model'].unique()
    model_order = get_model_order()
    models = [m for m in model_order if m in available_models]
    if not models:
        print('No models found in data.')
        return
    # Use all available data (unpaired)
    df_used = df_all

    # Question counts per model (on intersection)
    q_counts = {}
    for m in models:
        sub = df_used[df_used['model']==m]
        q_counts[m] = len(set(zip(sub['dataset'], sub['question_id'])))
    # Metrics
    metrics = [
        ('rqi', 'RQI'),
        ('turns_to_first_sufficient', 'TurnsToFirstSuff'),
        ('refined_rate', 'Refined%'),
        ('repeat_rate', 'Repeat%'),
        ('success', 'Success%'),
    ]
    # Per-model bootstrap CIs
    print('\nPer-model means with 95% CIs (clustered by question):')
    header = f"{'Model':40s} {'Ques':>6s} {'RQI':>10s} {'Turns':>10s} {'Refined%':>10s} {'Repeat%':>10s} {'Success%':>10s}"
    print(header)
    print('-'*len(header))
    # Compute all metrics CI results once
    ci_cache = {m: {} for m in models}
    for met, _title in metrics:
        res = cluster_bootstrap_ci_by_model(df_used, met, n_boot=n_boot)
        for m in models:
            mean, lo, hi = res.get(m, (np.nan, np.nan, np.nan))
            if met in {'refined_rate','repeat_rate','success'}:
                mean = mean*100.0 if not np.isnan(mean) else np.nan
                lo = lo*100.0 if not np.isnan(lo) else np.nan
                hi = hi*100.0 if not np.isnan(hi) else np.nan
            ci_cache[m][met] = (mean, lo, hi)
    for m in models:
        qn = q_counts.get(m, 0)
        rqi_m = ci_cache[m]['rqi']; trn = ci_cache[m]['turns_to_first_sufficient']
        refp = ci_cache[m]['refined_rate']; rep = ci_cache[m]['repeat_rate']; succ = ci_cache[m]['success']
        def fmt(triple):
            mean, lo, hi = triple
            return '   NA    ' if np.isnan(mean) else f"{mean:5.2f}[{lo:5.2f},{hi:5.2f}]"
        line = f"{m:40s} {qn:6d} {fmt(rqi_m):>10s} {fmt(trn):>10s} {fmt(refp):>10s} {fmt(rep):>10s} {fmt(succ):>10s}"
        print(line)

    # Action mix table per model
    print('\nAction mix (% of search turns) per model:')
    print(f"{'Model':40s} {'Initial':>8s} {'Refined':>8s} {'Follow-up':>10s} {'Repeat':>8s}")
    for m in models:
        mix = compute_action_mix(df_used[df_used['model']==m])
        print(f"{m:40s} {mix['Initial']:8.1f} {mix['Refined']:8.1f} {mix['Follow-up']:10.1f} {mix['Repeat']:8.1f}")

    # Step-weighted RQI (ratio-of-sums) for reference
    print('\nStep-weighted RQI (ratio-of-sums over reasoning steps):')
    print(f"{'Model':40s} {'RQI_step_weighted':>18s}")
    step_weighted = {}
    for m in models:
        numer = 0
        denom = 0
        for _, row in df_used[df_used['model']==m].iterrows():
            rqi = row['rqi']
            steps = int(row['total_turns']) if not pd.isna(row['total_turns']) else 0
            # approximate step weighting by total reasoning steps within trajectory is not stored;
            # fall back to weighting by total_turns as proxy; document limitation
            if not pd.isna(rqi) and steps>0:
                numer += rqi * steps
                denom += steps
        step_weighted[m] = (numer/denom) if denom>0 else np.nan
        val = step_weighted[m]
        print(f"{m:40s} {('   NA    ' if np.isnan(val) else f'{val:8.3f}'):>18s}")
    
    # Reasoning type grounded ratios per model (intersection)
    print('\nReasoning type grounded ratios per model:')
    all_reasoning_types = set()
    model_reasoning_data = {}
    
    for m in models:
        sub_df = df_used[df_used['model'] == m]
        reasoning_stats = aggregate_rqi_by_reasoning_type(sub_df)
        model_reasoning_data[m] = reasoning_stats
        all_reasoning_types.update(reasoning_stats.keys())
    
    if all_reasoning_types:
        reasoning_types = sorted(all_reasoning_types)
        # Print header
        header = f"{'Model':40s}"
        for rt in reasoning_types:
            header += f" {rt[:8]:>8s}"
        print(header)
        print('-' * len(header))
        
        # Print data for each model
        for m in models:
            line = f"{m:40s}"
            for rt in reasoning_types:
                stats = model_reasoning_data[m].get(rt, {})
                ratio = stats.get('grounded_ratio', np.nan)
                count = stats.get('total_count', 0)
                if np.isnan(ratio) or count == 0:
                    line += f" {'--':>8s}"
                else:
                    line += f" {ratio:7.2f}"
            print(line)

    # Type macro-average and standardized RQI
    print('\nType macro-average and standardized RQI (intersection):')
    # Build per-model per-type grounded rates
    type_list = ["InformationSynthesis", "PlanFormation", "StateAssessment"]
    # Reference distribution: pooled over models on intersection
    pooled_counts = {t: 0 for t in type_list}
    for m in models:
        sub_df = df_used[df_used['model'] == m]
        stats = aggregate_rqi_by_reasoning_type(sub_df)
        for t in type_list:
            pooled_counts[t] += stats.get(t, {}).get('total_count', 0)
    total = sum(pooled_counts.values()) or 1
    ref_weights = {t: (pooled_counts[t] / total) for t in type_list}

    print(f"{'Model':40s} {'MacroAvg':>8s} {'Std(w_ref)':>10s}")
    for m in models:
        stats = model_reasoning_data[m]
        rates = {t: stats.get(t, {}).get('grounded_ratio', np.nan) for t in type_list}
        # macro-average (equal weight over types with available data)
        valid = [r for r in rates.values() if not np.isnan(r)]
        macro = np.mean(valid) if valid else np.nan
        # standardized to ref_weights
        std = 0.0
        for t in type_list:
            r = rates.get(t, np.nan)
            if not np.isnan(r):
                std += ref_weights[t] * r
        print(f"{m:40s} {(f'{macro:6.3f}' if not np.isnan(macro) else '  NA  '):>8s} {(f'{std:8.3f}' if not np.isnan(std) else '    NA   '):>10s}")
    
    print('='*72)
    return


# ---------------------------
# Standardized success by RQI bins (direct standardization)
# ---------------------------

# (Removed) Standardized success helpers previously printed a pooled-RQI-bin table


def debug_grounding_comparison(traces: list):
    """Print raw grounding counts per model to debug low RQI (e.g., SearchR1).
    NOTE: In this context, 'Grounded' strictly means groundness='grounded' AND anchor_type='EVIDENCE'.
    """
    from collections import Counter
    eligible_types = {"InformationSynthesis", "PlanFormation", "StateAssessment"}
    counts = defaultdict(lambda: {
        'total': 0,
        'grounded': 0,
        'type_total': Counter(),
        'type_grounded': Counter(),
        'grounding_vals': Counter(),
    })
    for t in traces:
        model_clean, cat = clean_and_categorize_model(t.get('model', ''))
        if cat == 'Other':
            continue
        for step in (t.get('trace', []) or []):
            ann = step.get('annotation', {})
            if not isinstance(ann, dict):
                continue
            
            rt = ann.get('type', '')
            
            is_reasoning_step = False
            if rt in eligible_types:
                is_reasoning_step = True
            elif cat == 'DeepResearch' and step.get('type') == 'search':
                is_reasoning_step = True
                # Map search to PlanFormation for consistent counting with rqi_by_type
                rt = "PlanFormation"

            if not is_reasoning_step:
                continue

            attrs = (ann.get('attributes', {}) or {})
            graw = str(attrs.get('groundness', '')).strip()
            glow = graw.lower()
            anchor = str(attrs.get('anchor_type', '')).upper()
            c = counts[model_clean]            
            c['type_total'][rt] += 1
            c['grounding_vals'][graw if graw else '(missing)'] += 1
            if anchor == 'EVIDENCE':
                c['total'] += 1
                if glow == 'grounded':
                    c['grounded'] += 1
                    c['type_grounded'][rt] += 1
    print("\n=== Grounding Debug: raw counts by model ===")
    print(f"{'Model':25s} {'ReasoningSteps':>14s} {'Grounded':>10s} {'RQI':>6s}")
    for m in get_model_order():
        if m not in counts:
            continue
        c = counts[m]
        total = int(c['total']); grounded = int(c['grounded'])
        rqi = (grounded/total) if total>0 else np.nan
        print(f"{m:25s} {total:14d} {grounded:10d} {rqi:6.2f}")
    # Focus: compare SearchR1 vs Base (Qwen)
    for m in ["SearchR1", "Base (Qwen)"]:
        if m not in counts:
            continue
        c = counts[m]
        print(f"\n[Debug] {m} grounding label distribution (top 8):")
        for val, cnt in c['grounding_vals'].most_common(8):
            print(f"  {val}: {cnt}")
        print(f"[Debug] {m} per-type grounded ratios:")
        for rt in ["InformationSynthesis", "PlanFormation", "StateAssessment"]:
            tt = int(c['type_total'][rt])
            gg = int(c['type_grounded'][rt])
            ratio = (gg/tt) if tt>0 else np.nan
            print(f"  {rt}: {ratio:.2f} (n={tt})")


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', type=str, default='final_annotated_traces.jsonl')
    ap.add_argument('--outdir', type=str, default='figs_cohort')
    ap.add_argument('--require_clear_for_sufficient', action='store_true')
    ap.add_argument('--exclude_pre_sufficient_answers', action='store_true')
    # no exclude_trivial toggle; all reasoning steps are counted
    ap.add_argument('--n_boot', type=int, default=2000, help='Bootstrap resamples (default 2000; use 5000 for final)')
    return ap.parse_args()

def main():
    args = parse_args()
    ensure_dir(args.outdir)
    traces = load_traces(args.input)
    print(f"Loaded {len(traces)} traces")

    df = build_trajectory_df(
        traces,
        require_clear_sufficient=args.require_clear_for_sufficient,
        exclude_pre_suff_answers=args.exclude_pre_sufficient_answers,
    )
    print("Trajectory rows:", len(df))
    print(df)
    # print("Cohort candidates:", Counter(df['model']))

    # No pairing: use all data directly
    df_paired_all = df

    # Debug grounding counts per model (focus on SearchR1)
    print("Grounding debug...")
    debug_grounding_comparison(traces)

    print("A1...")
    plot_A1_means(df_paired_all, args.outdir, n_boot=args.n_boot)
    print("Reasoning type grounded ratios...")
    plot_reasoning_type_grounded_ratios(df_paired_all, args.outdir)

    # RQI-E evidence-conditioned grounding propensity (unpaired; keep all)
    print("RQI-E: building step-level reasoning dataframe...")
    step_df_all = build_reasoning_step_df(traces)
    if not step_df_all.empty:
        models_keep = set(df_paired_all['model'].unique())
        step_df_all = step_df_all[step_df_all['model'].isin(models_keep)]
    print("RQI-E A...")
    plot_RQI_E_A_propensity(step_df_all, args.outdir, n_boot=args.n_boot)
    print("RQI-E A (enhanced bars)...")
    plot_RQI_E_A_enhanced_bar(step_df_all, args.outdir, n_boot=args.n_boot)
    print("RQI-E B...")
    plot_RQI_E_B_by_type(step_df_all, args.outdir, n_boot=args.n_boot)
    print("RQI-E B (enhanced bars by type)...")
    plot_RQI_E_B_enhanced_by_type(step_df_all, args.outdir, n_boot=args.n_boot)

    # Structured console summary
    print_summary_results(df_paired_all, args.outdir, n_boot=args.n_boot)

    # (Removed) Standardized success by pooled RQI-bin distribution

    # Reporting checklist dump (unpaired)
    with open(os.path.join(args.outdir, 'reporting_checklist.txt'), 'w') as f:
        f.write("Reporting checklist\n")
        f.write("===================\n")
        # Totals and per-model counts
        total_questions = len(set(zip(df_paired_all['dataset'], df_paired_all['question_id'])))
        f.write(f"Total questions (union): {total_questions}\n")
        f.write(f"Trajectories: {len(df_paired_all)}\n")
        f.write(f"Models: {Counter(df_paired_all['model'])}\n")
        f.write("\nDefinitions:\n- RQI = fraction of reasoning steps (InformationSynthesis, PlanFormation, StateAssessment) with groundness=Grounded and anchor_type=EVIDENCE\n")
        f.write("- Turns-to-First-Sufficient: index of first search_result with Sufficient")
        f.write(" & Clear\n" if args.require_clear_for_sufficient else " (Sufficient only)\n")
        f.write("- RefinedQuery rate = #RefinedQuery / #search queries; RepeatQuery rate analogous\n")
        f.write("- Success: prefer is_correct; else reward; else presence of CorrectAnswer\n")
        f.write("\nBootstrap: 5k resamples, clustered by question\n")
        f.write(f"Sensitivity:\n- require_clear_for_sufficient={args.require_clear_for_sufficient}\n")
        f.write(f"- exclude_pre_sufficient_answers={args.exclude_pre_sufficient_answers}\n")
        # exclude_trivial_rqi is deprecated and ignored
    print(f"All figures saved to {args.outdir}/")

if __name__ == '__main__':
    main()