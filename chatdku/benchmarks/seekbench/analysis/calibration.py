#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
R3: Evidence strength per turn — Answer timing vs evidence
=========================================================

Ontology mapping (minimal, auditable):
- E=0 (Low): information_quality=Insufficient (any clarity)
- E=1 (Medium): information_quality=Sufficient & information_clarity != Clear
- E=2 (High): information_quality=Sufficient & information_clarity = Clear

Answer event: the FIRST time a trajectory emits an answer (CorrectAnswer or IncorrectAnswer). Ignore later revisions.

Policy (primary): should answer iff E >= 2 at the current turn.
Sensitivity: threshold E >= 1.

Units:
- Turn-level for propensities (A1–A2)
- Trajectory-level for premature/over-cautious (A3–A4)

Uncertainty: 5k bootstraps clustered by question (dataset, question_id).

Outputs (saved to outdir):
- fig_R3_D_calibration_rates.png
- fig_R3_E_timing.png

Usage:
  python calibration.py \
    --input final_annotated_traces.jsonl \
    --outdir figs_evidence \
    --n_boot 5000 \
    --horizon 15 \
    --policy_threshold high   # or: medium

Notes:
- A1/A2 are computed on pre-answer turns (inclusive of the answer turn) without horizon truncation.
- A3/A4 use the specified horizon (default 15) or end of trace if shorter.
"""

import os
import json
import argparse
from collections import defaultdict, Counter

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# Plotting style consistent with R1/R2
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

# Global model color palette (align with groundness/recovery analyses)
MODEL_COLOR_PALETTE = {
    'Qwen3-30B-A3B-Instruct-2507': '#460057',          
    'Qwen3-30B-A3B': '#1abc9c',
      
}

def get_model_color(model_name: str) -> str:
    return MODEL_COLOR_PALETTE.get(model_name, '#7f7f7f')

def get_model_order():
    return ["Qwen3-30B-A3B-Instruct-2507 (Qwen)", "Qwen3-30B-A3B'(Qwen)"]


def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)


def savefig(fig, outdir, name):
    ensure_dir(outdir)
    p1 = os.path.join(outdir, f'{name}.png')
    fig.tight_layout()
    fig.savefig(p1)
    print(f"Saved {p1}")
    plt.close(fig)


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


def load_traces(path: str):
    rows = []
    with open(path, 'r') as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


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


def get_evidence_at_turn(step: dict) -> int:
    """Get evidence level for a single turn only.
    Returns the evidence level from this specific turn's search result.
    """
    ann = step.get('annotation', {})
    if isinstance(ann, dict) and ann.get('type') == 'search_result':
        attrs = (ann.get('attributes', {}) or {})
        return map_evidence_level(attrs.get('information_quality'), attrs.get('information_clarity'))
    return 0


def build_turn_level_df(traces: list) -> pd.DataFrame:
    """Build per-turn records up to the first answer event (inclusive) for each trajectory.
    Fields: model, category, dataset, question_id, step_index, E, answer_event, correct_event
    E is cumulative best evidence up to the current turn.
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
                attrs = (ann.get('attributes', {}) or {})
                cur_E = max(cur_E, map_evidence_level(attrs.get('information_quality'), attrs.get('information_clarity')))

            # Determine if this turn is the first answer event
            ans_event = 0
            correct = np.nan
            if not answered and isinstance(ann, dict) and ann.get('type') in ('CorrectAnswer', 'IncorrectAnswer'):
                answered = True
                ans_event = 1
                correct = 1 if ann.get('type') == 'CorrectAnswer' else 0

            rows.append({
                'model': model,
                'category': cat,
                'dataset': dataset,
                'question_id': qid,
                'step_index': i,
                'E': cur_E,
                'answer_event': ans_event,
                'correct_event': correct,
            })

            # stop collecting turns after the first answer event
            if ans_event == 1:
                break
    return pd.DataFrame(rows)

def build_answer_event_df(turn_df: pd.DataFrame) -> pd.DataFrame:
    """Derive per-trajectory first answer event with E at answer and correctness.
    Returns columns: model, category, dataset, question_id, E_at_answer, correct
    """
    ans = turn_df[turn_df['answer_event'] == 1].copy()
    # Ensure one row per (dataset, question_id, model)
    ans = ans.sort_values(['dataset','question_id','model','step_index'])
    ans = ans.groupby(['dataset','question_id','model','category'], as_index=False).first()
    ans = ans.rename(columns={'E':'E_at_answer', 'correct_event':'correct'})
    # Normalize correctness to {0,1}
    ans['correct'] = ans['correct'].fillna(0).astype(int)
    return ans[['model','category','dataset','question_id','E_at_answer','correct']]

def ordinal_auc_from_counts(pos_counts, neg_counts):
    """Compute AUC for ordinal scores 0/1/2 from per-score counts.
    pos_counts, neg_counts: dict score->count
    """
    scores = [0,1,2]
    n_pos = sum(pos_counts.get(s,0) for s in scores)
    n_neg = sum(neg_counts.get(s,0) for s in scores)
    if n_pos == 0 or n_neg == 0:
        return np.nan
    better = 0
    ties = 0
    for sp in scores:
        for sn in scores:
            if sp > sn:
                better += pos_counts.get(sp,0) * neg_counts.get(sn,0)
            elif sp == sn:
                ties += pos_counts.get(sp,0) * neg_counts.get(sn,0)
    auc = (better + 0.5*ties) / (n_pos * n_neg)
    return auc

def clustered_auc_ci(answer_df: pd.DataFrame, group_mask: pd.Series, n_boot=2000, seed=42):
    """Cluster-bootstrap AUC of E_at_answer predicting correctness among answered events.
    Cluster by (dataset, question_id). group_mask selects subset (e.g., a model or category).
    """
    rng = np.random.default_rng(seed)
    sub = answer_df[group_mask].copy()
    if sub.empty:
        return (np.nan, np.nan, np.nan)
    sub['cluster'] = list(zip(sub['dataset'], sub['question_id']))
    clusters = sorted(sub['cluster'].unique())
    # Pre-aggregate counts by cluster and score
    pos_by_cluster = {c: Counter() for c in clusters}
    neg_by_cluster = {c: Counter() for c in clusters}
    for _, r in sub.iterrows():
        c = r['cluster']; s = int(r['E_at_answer']); y = int(r['correct'])
        if y == 1:
            pos_by_cluster[c][s] += 1
        else:
            neg_by_cluster[c][s] += 1
    # Point estimate (all clusters)
    pos_counts = Counter(); neg_counts = Counter()
    for c in clusters:
        pos_counts.update(pos_by_cluster[c]); neg_counts.update(neg_by_cluster[c])
    point = ordinal_auc_from_counts(pos_counts, neg_counts)
    # Bootstrap
    n = len(clusters)
    idx = rng.integers(0, n, size=(n_boot, n))
    samp = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        sel = idx[i]
        pos_counts_b = Counter(); neg_counts_b = Counter()
        for sidx in sel:
            c = clusters[sidx]
            pos_counts_b.update(pos_by_cluster[c]); neg_counts_b.update(neg_by_cluster[c])
        samp[i] = ordinal_auc_from_counts(pos_counts_b, neg_counts_b)
    lo, hi = float(np.nanpercentile(samp, 2.5)), float(np.nanpercentile(samp, 97.5))
    return point, lo, hi

def clustered_or_ci(answer_df: pd.DataFrame, group_mask: pd.Series, n_boot=2000, seed=42):
    """Cluster-bootstrap odds ratio of correctness at E=2 vs E=0 among answered events.
    Uses 0.5 continuity correction for zero cells. Returns (point, lo, hi).
    """
    rng = np.random.default_rng(seed)
    sub = answer_df[group_mask].copy()
    if sub.empty:
        return (np.nan, np.nan, np.nan)
    sub['cluster'] = list(zip(sub['dataset'], sub['question_id']))
    clusters = sorted(sub['cluster'].unique())
    def or_from_counts(c2_pos, c2_neg, c0_pos, c0_neg):
        a = c2_pos + 0.5; b = c2_neg + 0.5; c = c0_pos + 0.5; d = c0_neg + 0.5
        return (a/b) / (c/d)
    # point
    c2_pos = c2_neg = c0_pos = c0_neg = 0
    for c in clusters:
        cl = sub[sub['cluster']==c]
        e2 = cl[cl['E_at_answer']==2]; e0 = cl[cl['E_at_answer']==0]
        c2_pos += int(e2['correct'].sum()); c2_neg += int(len(e2) - e2['correct'].sum())
        c0_pos += int(e0['correct'].sum()); c0_neg += int(len(e0) - e0['correct'].sum())
    point = or_from_counts(c2_pos, c2_neg, c0_pos, c0_neg)
    # bootstrap
    n = len(clusters)
    idx = rng.integers(0, n, size=(n_boot, n))
    samp = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        sel = idx[i]
        c2p=c2n=c0p=c0n=0
        for sidx in sel:
            c = clusters[sidx]
            cl = sub[sub['cluster']==c]
            e2 = cl[cl['E_at_answer']==2]; e0 = cl[cl['E_at_answer']==0]
            c2p += int(e2['correct'].sum()); c2n += int(len(e2) - e2['correct'].sum())
            c0p += int(e0['correct'].sum()); c0n += int(len(e0) - e0['correct'].sum())
        samp[i] = or_from_counts(c2p, c2n, c0p, c0n)
    lo, hi = float(np.nanpercentile(samp, 2.5)), float(np.nanpercentile(samp, 97.5))
    return point, lo, hi

def clustered_slope_ci(answer_df: pd.DataFrame, group_mask: pd.Series, n_boot=2000, seed=42):
    """Cluster-bootstrap slope of accuracy vs E level (0,1,2) among answered events.
    Slope computed from mean accuracies at E=0,1,2 via least-squares line.
    """
    rng = np.random.default_rng(seed)
    sub = answer_df[group_mask].copy()
    if sub.empty:
        return (np.nan, np.nan, np.nan)
    sub['cluster'] = list(zip(sub['dataset'], sub['question_id']))
    clusters = sorted(sub['cluster'].unique())
    def slope_from_acc(acc):
        x = np.array([0,1,2], dtype=float)
        y = np.array([acc.get(0,np.nan), acc.get(1,np.nan), acc.get(2,np.nan)], dtype=float)
        # simple least-squares on available points
        mask = ~np.isnan(y)
        if mask.sum() < 2:
            return np.nan
        xm = x[mask].mean(); ym = y[mask].mean()
        num = np.sum((x[mask]-xm)*(y[mask]-ym))
        den = np.sum((x[mask]-xm)**2)
        return num/den if den>0 else np.nan
    # helper to compute accuracies pooled across clusters
    def pooled_acc(cl_sel):
        acc = {}
        for k in [0,1,2]:
            kdf = sub[sub['E_at_answer']==k]
            kdf = kdf[kdf['cluster'].isin(cl_sel)]
            if len(kdf)==0:
                acc[k]=np.nan
                continue
            acc[k] = float(kdf['correct'].mean())
        return acc
    # point
    acc_point = pooled_acc(clusters)
    point = slope_from_acc(acc_point)
    # bootstrap
    n = len(clusters)
    idx = rng.integers(0, n, size=(n_boot, n))
    samp = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        sel = [clusters[s] for s in idx[i]]
        acc_b = pooled_acc(sel)
        samp[i] = slope_from_acc(acc_b)
    lo, hi = float(np.nanpercentile(samp, 2.5)), float(np.nanpercentile(samp, 97.5))
    return point, lo, hi

def analyze_correctness_vs_E_rigorous(turn_df: pd.DataFrame, outdir: str, n_boot=2000):
    """Rigorous analysis of relationship between E and final answer correctness.
    Reports per-model P(correct|answer,E=k) with 95% CI, trend slope, odds ratio (E=2 vs E=0), and AUC.
    Also saves a per-model bar plot by E.
    """
    print("\n" + "="*80)
    print("R3-RIGOROUS: RELATIONSHIP BETWEEN E AND FINAL ANSWER CORRECTNESS")
    print("="*80)
    ans_df = build_answer_event_df(turn_df)
    if ans_df.empty:
        print("No answered events found; skipping rigorous analysis.")
        return
    # Compute per-model metrics
    models_present = [m for m in get_model_order() if m in ans_df['model'].unique()]
    # Figure: bars per E for each model
    fig, axes = plt.subplots(1, 3, figsize=(14,4), sharey=True)
    for e_idx, k in enumerate([0,1,2]):
        ax = axes[e_idx]
        vals = []
        los = []
        his = []
        for m in models_present:
            sub = ans_df[(ans_df['model']==m) & (ans_df['E_at_answer']==k)].copy()
            sub['cluster'] = list(zip(sub['dataset'], sub['question_id']))
            numer = defaultdict(float); denom = defaultdict(float)
            for _, r in sub.iterrows():
                c = r['cluster']; denom[c] += 1.0; numer[c] += float(r['correct'])
            p, lo, hi = clustered_ratio_ci(numer, denom, n_boot=n_boot)
            vals.append(p); los.append(lo); his.append(hi)
        x = np.arange(len(models_present))
        yerr = np.vstack([np.array(vals)-np.array(los), np.array(his)-np.array(vals)])
        ax.bar(x, np.nan_to_num(vals, nan=0.0), color=[get_model_color(m) for m in models_present])
        ax.errorbar(x, vals, yerr=yerr, fmt='none', ecolor='black', capsize=3)
        ax.set_title(f'Accuracy at E={k}')
        ax.set_xticks(x); ax.set_xticklabels(models_present, rotation=45, ha='right')
        if e_idx == 0:
            ax.set_ylabel('P(correct | answer, E)')
        ax.set_ylim(0, 1.0)
        ax.grid(axis='y', alpha=0.3)
    fig.suptitle('Accuracy by evidence at answer, per model (95% CI)')
    plt.tight_layout()
    savefig(fig, outdir, 'fig_R3_B_quality_by_model')

    # Textual rigorous stats per model
    print("\nPer-model rigorous statistics:")
    print(f"{'Model':25s} {'Slope':>8s} {'[lo,hi]':>18s} {'OR(E2/E0)':>12s} {'[lo,hi]':>18s} {'AUC':>8s} {'[lo,hi]':>18s}")
    for m in models_present:
        mask = (ans_df['model']==m)
        slope_p, slope_lo, slope_hi = clustered_slope_ci(ans_df, mask, n_boot=n_boot)
        or_p, or_lo, or_hi = clustered_or_ci(ans_df, mask, n_boot=n_boot)
        auc_p, auc_lo, auc_hi = clustered_auc_ci(ans_df, mask, n_boot=n_boot)
        print(f"{m:25s} {slope_p:8.3f} [{slope_lo:5.3f},{slope_hi:5.3f}] {or_p:12.2f} [{or_lo:6.2f},{or_hi:6.2f}] {auc_p:8.3f} [{auc_lo:5.3f},{auc_hi:5.3f}]")


def build_trajectory_level_df(traces: list, horizon: int) -> pd.DataFrame:
    """Per-trajectory summary for A3/A4 at a given horizon.
    Fields: model, category, dataset, question_id, answered_within_h, ans_at_step, E_at_answer, ever_high_within_h
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
        H = min(horizon, len(steps))
        cur_E = 0
        ans_step = None
        E_at_answer = None
        ever_high = False
        for i in range(H):
            # E = max of all evidence seen so far
            turn_E = get_evidence_at_turn(steps[i] if i < len(steps) else {})
            cur_E = max(cur_E, turn_E)
            if cur_E >= 2:
                ever_high = True
            
            ann = steps[i].get('annotation', {}) if i < len(steps) else {}
            if ans_step is None and isinstance(ann, dict) and ann.get('type') in ('CorrectAnswer', 'IncorrectAnswer'):
                ans_step = i
                E_at_answer = cur_E
                # Do not break; keep scanning to maintain ever_high status within H
        rows.append({
            'model': model,
            'category': cat,
            'dataset': dataset,
            'question_id': qid,
            'answered_within_h': 1 if ans_step is not None else 0,
            'ans_at_step': ans_step if ans_step is not None else np.nan,
            'E_at_answer': E_at_answer if E_at_answer is not None else np.nan,
            'ever_high_within_h': 1 if ever_high else 0,
        })
    return pd.DataFrame(rows)


# ---------------------------
# Cluster bootstrap utilities
# ---------------------------

def clustered_ratio_ci(numer_by_cluster: dict, denom_by_cluster: dict, n_boot=5000, seed=42):
    """Bootstrap CI for a ratio of sums across clusters.
    numer_by_cluster, denom_by_cluster: dict cluster_id -> float
    Returns (point, lo, hi)
    """
    rng = np.random.default_rng(seed)
    clusters = list(denom_by_cluster.keys())
    if not clusters:
        return (np.nan, np.nan, np.nan)
    # ensure numer has zeros for missing clusters
    numer = np.array([float(numer_by_cluster.get(c, 0.0)) for c in clusters])
    denom = np.array([float(denom_by_cluster.get(c, 0.0)) for c in clusters])
    # point estimate
    num_sum = float(numer.sum())
    den_sum = float(denom.sum())
    point = (num_sum / den_sum) if den_sum > 0 else np.nan
    # bootstrap
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


# ---------------------------
# Combined: R3-A + R3-B into one figure
# ---------------------------
def analyze_AB_combined(turn_df: pd.DataFrame, outdir: str, n_boot=5000):
    """Combine R3-A and R3-B into a single axes (Base/Few-shot aggregated, RL Agents aggregated)."""
    print("\n" + "="*60)
    print("R3-AB: SINGLE-AXES OVERLAY (lines + bar series)")
    print("="*60)

    categories_present = set(turn_df['category'].dropna().unique().tolist())
    if not categories_present:
        print("No categories found in data, skipping R3-AB plot")
        return

    # Build group definitions
    groups = []
    if 'Base' in categories_present:
        groups.append({'label': 'Base (Qwen)', 'type': 'category', 'value': 'Base'})
    if 'Few-shot' in categories_present:
        groups.append({'label': 'Few-shot (Qwen)', 'type': 'category', 'value': 'Few-shot'})
    if 'RL Agents' in categories_present:
        groups.append({'label': 'RL Agents', 'type': 'category', 'value': 'RL Agents'})
    if 'CoT (Qwen)' in categories_present:
        groups.append({'label': 'CoT (Qwen)', 'type': 'category', 'value': 'CoT (Qwen)'})
    if 'ReAct (Qwen)' in categories_present:
        groups.append({'label': 'ReAct (Qwen)', 'type': 'category', 'value': 'ReAct (Qwen)'})

    if not groups:
        print("No valid groups for plotting, skipping R3-AB plot")
        return

    labels = ['E=0', 'E=1', 'E=2']
    x = np.array([0, 1, 2])

    fig, ax_left = plt.subplots(1, 1, figsize=(8, 4))
    ax_right = ax_left.twinx()

    n_groups = len(groups)
    if n_groups == 1:
        width = 0.3
        offsets = [0.0]
    elif n_groups == 2:
        width = 0.25
        offsets = [-width/2, width/2]
    else:
        width = 0.18
        base_offset = -width if n_groups == 3 else -width * (n_groups - 1) / 2
        offsets = [base_offset + i * width for i in range(n_groups)]

    # First draw all bars (P(correct|answer,E))
    for i, grp in enumerate(groups):
        if grp['type'] == 'category':
            sub = turn_df[turn_df['category'] == grp['value']].copy()
        else:
            sub = turn_df[turn_df['model'] == grp['value']].copy()
        if sub.empty:
            continue
        sub['cluster'] = list(zip(sub['dataset'], sub['question_id']))

        # P(correct|answer,E)
        ans_only = sub[sub['answer_event'] == 1].copy()
        qual_points, qual_lo, qual_hi = [], [], []
        for k in [0, 1, 2]:
            k_df = ans_only[ans_only['E'] == k]
            if len(k_df) == 0:
                qual_points.append(np.nan); qual_lo.append(np.nan); qual_hi.append(np.nan); continue
            numer = defaultdict(float); denom = defaultdict(float)
            for _, row in k_df.iterrows():
                c = row['cluster']; denom[c] += 1.0
                val = row['correct_event']
                is_correct = 0.0 if (val is np.nan or pd.isna(val)) else float(val)
                numer[c] += is_correct
            p, lo, hi = clustered_ratio_ci(numer, denom, n_boot=n_boot)
            qual_points.append(p); qual_lo.append(lo); qual_hi.append(hi)
        qual_points = np.array(qual_points)
        yerr_qual = np.vstack([qual_points - np.array(qual_lo), np.array(qual_hi) - qual_points])
        color = get_model_color(grp['label']) if grp['label'] in MODEL_COLOR_PALETTE else '#555555'
        ax_right.bar(x + offsets[i], np.nan_to_num(qual_points, nan=0.0),
                     width=width*0.95, color=color, label=f'{grp["label"]} (P(correct|answer,E))')
        ax_right.errorbar(x + offsets[i], qual_points, yerr=yerr_qual, fmt='none', capsize=3, color='black')

    # Then draw all lines (P(answer|E))
    for i, grp in enumerate(groups):
        if grp['type'] == 'category':
            sub = turn_df[turn_df['category'] == grp['value']].copy()
        else:
            sub = turn_df[turn_df['model'] == grp['value']].copy()
        if sub.empty:
            continue
        sub['cluster'] = list(zip(sub['dataset'], sub['question_id']))

        # P(answer|E)
        prop_points, prop_lo, prop_hi = [], [], []
        for k in [0, 1, 2]:
            k_df = sub[sub['E'] == k]
            if len(k_df) == 0:
                prop_points.append(np.nan); prop_lo.append(np.nan); prop_hi.append(np.nan); continue
            numer = defaultdict(float); denom = defaultdict(float)
            for _, row in k_df.iterrows():
                c = row['cluster']; denom[c] += 1.0; numer[c] += float(row['answer_event'])
            p, lo, hi = clustered_ratio_ci(numer, denom, n_boot=n_boot)
            prop_points.append(p); prop_lo.append(lo); prop_hi.append(hi)
        prop_points = np.array(prop_points)
        yerr_prop = np.vstack([prop_points - np.array(prop_lo), np.array(prop_hi) - prop_points])
        color = get_model_color(grp['label']) if grp['label'] in MODEL_COLOR_PALETTE else '#555555'
        ax_left.errorbar(x, prop_points, yerr=yerr_prop, fmt='o-', capsize=3,
                         color=color, label=f'{grp["label"]} (P(answer|E))')

    # Axes setup
    ax_left.set_xticks(x); ax_left.set_xticklabels(labels)
    ax_left.set_ylabel('P(answer | E)')
    ax_right.set_ylabel('P(correct | answer, E)')
    ax_left.set_ylim(0, 0.25)
    ax_right.set_ylim(0, 0.5)
    ax_left.set_title('R3-A+B: Propensity (lines) and Quality (bars) by Evidence')
    # Legend: use proxy artists to avoid incorrect labels from containers
    line_proxies = [Line2D([0], [0], color=get_model_color(grp['label']) if grp['label'] in MODEL_COLOR_PALETTE else '#555555',
                           marker='o', linestyle='-', label=grp['label'])
                    for grp in groups]
    bar_proxies = [Patch(facecolor=get_model_color(grp['label']) if grp['label'] in MODEL_COLOR_PALETTE else '#555555',
                         label=grp['label'])
                   for grp in groups]
    
    # Add labels for metrics only once
    line_label = Line2D([0], [0], color='none', marker='', linestyle='', label="P(answer|E)")
    bar_label = Patch(facecolor='none', edgecolor='none', label="P(correct|answer,E)")
    
    handles = line_proxies + [line_label] + bar_proxies + [bar_label]
    ax_left.legend(handles=handles, loc='upper left', fontsize=8, ncol=2, frameon=True)

    fig.tight_layout()
    savefig(fig, outdir, 'fig_R3_AB_combined')


# ---------------------------
# A3: Calibration confusion plot (should vs did)
# ---------------------------

def compute_confusion_data(traj_df: pd.DataFrame, policy_threshold: str = 'high', group_by: str = 'category'):
    """Compute confusion matrix data for TP/FP/FN/TN per archetype without plotting.
    policy_threshold: 'high' => E>=2, 'medium' => E>=1
    """
    thr = 2 if policy_threshold == 'high' else 1
    
    # We'll support grouping by 'category' (default) or 'model'
    valid_groups = ['category', 'model']
    if group_by not in valid_groups:
        group_by = 'category'
    # Get actual categories from data if grouping by category
    categories = []
    if group_by == 'category':
        categories = traj_df['category'].dropna().unique().tolist()
    # classify per trajectory
    rows = []
    for _, r in traj_df.iterrows():
        cat = r.get('category', None)
        grp_val = r.get(group_by, None)
        if group_by == 'category':
            if cat not in categories:
                continue
        answered = int(r['answered_within_h'])
        ans_E = int(r['E_at_answer']) if not pd.isna(r['E_at_answer']) else -1
        ever_high = int(r['ever_high_within_h'])
        # label
        if answered:
            if ans_E >= thr:
                lab = 'TP'  # Good answers
            else:
                lab = 'FP'  # Premature
        else:
            if ever_high:
                lab = 'FN'  # Over-cautious
            else:
                lab = 'TN'  # Good deferral
        rows.append({'category': cat, 'model': r.get('model', None), 'dataset': r['dataset'], 'question_id': r['question_id'], 'label': lab, group_by: grp_val})
    return pd.DataFrame(rows)

# ---------------------------
# A4: Calibration error + key rates
# ---------------------------

def compute_A4_calibration(turn_df: pd.DataFrame, confusion_df: pd.DataFrame, policy_threshold: str='high', n_boot=5000, group_by: str = 'category', ce_prevalence: str = 'global'):
    thr = 2 if policy_threshold == 'high' else 1
    # determine groups
    if group_by == 'category':
        groups = sorted(turn_df['category'].dropna().unique().tolist())
    else:
        groups = sorted(turn_df['model'].dropna().unique().tolist())
    # Compute global/reference prevalence w_ref(k) if requested
    ce_prevalence = ce_prevalence if ce_prevalence in ['global','group'] else 'global'
    # Global prevalence across all turns (cluster-weighted)
    denom_all_global = defaultdict(float)
    denom_k_global = {0: defaultdict(float), 1: defaultdict(float), 2: defaultdict(float)}
    tmp_all = turn_df.copy()
    tmp_all['cluster'] = list(zip(tmp_all['dataset'], tmp_all['question_id']))
    for _, row in tmp_all.iterrows():
        c = row['cluster']
        denom_all_global[c] += 1.0
        k = int(row['E']) if not pd.isna(row['E']) else -1
        if k in denom_k_global:
            denom_k_global[k][c] += 1.0
    w_ref = {}
    for k in [0,1,2]:
        w_point_ref, _, _ = clustered_ratio_ci(denom_k_global[k], denom_all_global, n_boot=n_boot)
        w_ref[k] = (w_point_ref or 0.0)

    results = []
    for cat in groups:
        if group_by == 'category':
            sub = turn_df[turn_df['category'] == cat].copy()
        else:
            sub = turn_df[turn_df['model'] == cat].copy()
        sub['cluster'] = list(zip(sub['dataset'], sub['question_id']))
        # P(answer|E=k)
        p_by_k = {}
        w_by_k = {}
        for k in [0,1,2]:
            k_df = sub[sub['E'] == k]
            numer = defaultdict(float); denom = defaultdict(float)
            for _, row in k_df.iterrows():
                c = row['cluster']
                denom[c] += 1.0
                numer[c] += float(row['answer_event'])
            p, lo, hi = clustered_ratio_ci(numer, denom, n_boot=n_boot)
            p_by_k[k] = (p, lo, hi)
            # prevalence w_k
            # compute as share of steps with E=k among all pre-answer steps
            denom_all = defaultdict(float)
            denom_k = defaultdict(float)
            for _, row in sub.iterrows():
                c = row['cluster']
                denom_all[c] += 1.0
            for _, row in k_df.iterrows():
                c = row['cluster']
                denom_k[c] += 1.0
            w_point, w_lo, w_hi = clustered_ratio_ci(denom_k, denom_all, n_boot=n_boot)
            w_by_k[k] = (w_point, w_lo, w_hi)

        # CE = sum_k w(k) * |P(answer|E=k) - 1[k>=thr]|
        ce_point = 0.0
        ce_parts = {}
        diffs_by_k = {}
        for k in [0,1,2]:
            target = 1.0 if (k >= thr) else 0.0
            wk_group = (w_by_k[k][0] or 0.0)
            wk = w_ref[k] if ce_prevalence == 'global' else wk_group
            ak = (p_by_k[k][0] or 0.0)
            diff = abs(ak - target)
            part = wk * diff
            ce_parts[k] = part
            diffs_by_k[k] = diff
            ce_point += part

        # Balanced CCE (prevalence independent): average absolute deviation across k
        cce_balanced = np.nanmean([diffs_by_k.get(k, np.nan) for k in [0,1,2]])

        # Also compute CE under global reference prevalence for reporting
        ce_ref_point = 0.0
        for k in [0,1,2]:
            target = 1.0 if (k >= thr) else 0.0
            ak = (p_by_k[k][0] or 0.0)
            ce_ref_point += (w_ref[k]) * abs(ak - target)

        # Premature = FP share, Over-cautious = FN share from confusion_df
        conf_sub = confusion_df[confusion_df[group_by] == cat].copy()
        conf_sub['cluster'] = list(zip(conf_sub['dataset'], conf_sub['question_id']))
        denom = defaultdict(float); num_fp = defaultdict(float); num_fn = defaultdict(float)
        for _, r in conf_sub.iterrows():
            c = r['cluster']
            denom[c] += 1.0
            if r['label'] == 'FP':
                num_fp[c] += 1.0
            if r['label'] == 'FN':
                num_fn[c] += 1.0
        prem_point, prem_lo, prem_hi = clustered_ratio_ci(num_fp, denom, n_boot=n_boot)
        over_point, over_lo, over_hi = clustered_ratio_ci(num_fn, denom, n_boot=n_boot)

        results.append({
            group_by: cat,
            'CE_point': ce_point,
            'CE_ref': ce_ref_point,
            'CCE_balanced': cce_balanced,
            'premature_point': prem_point,
            'over_cautious_point': over_point,
            'premature_lo': prem_lo, 'premature_hi': prem_hi,
            'over_cautious_lo': over_lo, 'over_cautious_hi': over_hi,
            # CE breakdown components and supporting stats
            'ce_e0': ce_parts.get(0, np.nan),
            'ce_e1': ce_parts.get(1, np.nan),
            'ce_e2': ce_parts.get(2, np.nan),
            'w0': w_by_k[0][0], 'w1': w_by_k[1][0], 'w2': w_by_k[2][0],
            'a0': p_by_k[0][0], 'a1': p_by_k[1][0], 'a2': p_by_k[2][0],
        })
    return pd.DataFrame(results)


def plot_A4_calibration(results_df: pd.DataFrame, turn_df: pd.DataFrame, confusion_df: pd.DataFrame, outdir: str, group_by: str = 'category', policy_threshold: str = 'high', n_boot: int = 5000, ce_prevalence: str = 'global'):
    print("\n" + "="*60)
    print("R3-D: CALIBRATION ERROR + PREMATURE/OVER-CAUTIOUS RATES")
    print("="*60)
    
    fig, ax = plt.subplots(figsize=(8, 4))
    if group_by == 'category':
        cats = sorted(results_df['category'].dropna().unique().tolist())
        group_field = 'category'
    else:
        cats = results_df[group_by].dropna().tolist()
        group_field = group_by
    x = np.arange(len(cats)); width = 0.25
    
    print(f"\nDetailed Results (by {group_by}):")
    print(f"{'Model':<12} {'CE':<8} {'CE_ref':<8} {'CCE_bal':<10} {'Premature':<12} {'Over-cautious':<15} {'Total Error':<12} {'CE[E=0]':<10} {'CE[E=1]':<10} {'CE[E=2]':<10}")
    print("-" * 140)
    
    # CE bars (no CI from ratio-of-CIs; we report point)
    ce_vals = [results_df[results_df[group_field]==c]['CE_point'].iloc[0] if c in results_df[group_field].values else np.nan for c in cats]
    ax.bar(x - width, ce_vals, width, label='CE', color='#1f77b4')
    
    # Premature with CI
    prem_vals = [results_df[results_df[group_field]==c]['premature_point'].iloc[0] if c in results_df[group_field].values else np.nan for c in cats]
    prem_lo = [results_df[results_df[group_field]==c]['premature_lo'].iloc[0] if c in results_df[group_field].values else np.nan for c in cats]
    prem_hi = [results_df[results_df[group_field]==c]['premature_hi'].iloc[0] if c in results_df[group_field].values else np.nan for c in cats]
    ax.bar(x, prem_vals, width, label='Premature')
    ax.errorbar(x, prem_vals, yerr=[np.array(prem_vals)-np.array(prem_lo), np.array(prem_hi)-np.array(prem_vals)], fmt='none', color='black', capsize=4)
    
    # Over-cautious with CI
    over_vals = [results_df[results_df[group_field]==c]['over_cautious_point'].iloc[0] if c in results_df[group_field].values else np.nan for c in cats]
    over_lo = [results_df[results_df[group_field]==c]['over_cautious_lo'].iloc[0] if c in results_df[group_field].values else np.nan for c in cats]
    over_hi = [results_df[results_df[group_field]==c]['over_cautious_hi'].iloc[0] if c in results_df[group_field].values else np.nan for c in cats]
    ax.bar(x + width, over_vals, width, label='Over-cautious')
    ax.errorbar(x + width, over_vals, yerr=[np.array(over_vals)-np.array(over_lo), np.array(over_hi)-np.array(over_vals)], fmt='none', color='black', capsize=4)
    
    # Print detailed results (with CE breakdown) for categories
    for i, cat in enumerate(cats):
        ce = ce_vals[i]
        cce_bal = results_df[results_df[group_field]==cat]['CCE_balanced'].iloc[0] if cat in results_df[group_field].values else np.nan
        ce_ref = results_df[results_df[group_field]==cat]['CE_ref'].iloc[0] if cat in results_df[group_field].values else np.nan
        prem = prem_vals[i]
        over = over_vals[i]
        total_error = prem + over
        # CE parts
        ce_e0 = results_df[results_df[group_field]==cat]['ce_e0'].iloc[0] if cat in results_df[group_field].values else np.nan
        ce_e1 = results_df[results_df[group_field]==cat]['ce_e1'].iloc[0] if cat in results_df[group_field].values else np.nan
        ce_e2 = results_df[results_df[group_field]==cat]['ce_e2'].iloc[0] if cat in results_df[group_field].values else np.nan
        
        print(f"{cat:<12} {ce:<8.3f} {ce_ref:<8.3f} {cce_bal:<10.3f} {prem:<8.3f}[{prem_lo[i]:.3f},{prem_hi[i]:.3f}] {over:<8.3f}[{over_lo[i]:.3f},{over_hi[i]:.3f}] {total_error:<12.3f} {ce_e0:<10.3f} {ce_e1:<10.3f} {ce_e2:<10.3f}")
        
        # Interpretation guidance
        # Improved CE interpretation using breakdown
        if ce > 0.3:
            # Identify dominant source
            parts = {'E=0': ce_e0, 'E=1': ce_e1, 'E=2': ce_e2}
            dom_k = max(parts, key=lambda k: (parts[k] if not np.isnan(parts[k]) else -1))
            print(f"    ⚠️  HIGH calibration error: {ce:.1%} from ideal policy (dominant at {dom_k})")
            # If E=0 dominates: premature at low-evidence; E=2 dominates: under-answering at high-evidence; E=1: ambiguity handling
            if dom_k == 'E=0':
                print(f"    ▸ Driver: Excess answering under low evidence (raise threshold / tighten gating)")
            elif dom_k == 'E=2':
                print(f"    ▸ Driver: Under-responsiveness at high evidence (increase answer propensity at E=2)")
            else:
                print(f"    ▸ Driver: Behavior at medium evidence is misaligned (clarify policy around E=1)")
        if prem > 0.2:
            print(f"    ⚠️  HIGH premature rate: {prem:.1%} answer when shouldn't")
        if over > 0.2:
            print(f"    ⚠️  HIGH over-cautious rate: {over:.1%} don't answer when should")
        if total_error < 0.2:
            print(f"    ✅ GOOD overall calibration: {total_error:.1%} total error rate")
        
        # If grouping by category, also print per-model breakdown within this category
        if group_by == 'category':
            # Compute per-model results for this category
            models_in_cat = sorted(turn_df[turn_df['category'] == cat]['model'].dropna().unique().tolist())
            if len(models_in_cat) > 1:  # Only print breakdown if there are multiple models
                print(f"\n  Per-model breakdown for {cat}:")
                # Compute model-level calibration for all models, then filter to this category
                # Note: confusion_df contains 'model' column even when group_by='category'
                model_results_df = compute_A4_calibration(turn_df, confusion_df, policy_threshold=policy_threshold, n_boot=n_boot, group_by='model', ce_prevalence=ce_prevalence)
                # Filter to models in this category
                model_results_df = model_results_df[model_results_df['model'].isin(models_in_cat)]
                
                for _, model_row in model_results_df.iterrows():
                    model_name = model_row['model']
                    m_ce = model_row['CE_point']
                    m_ce_ref = model_row['CE_ref']
                    m_cce_bal = model_row['CCE_balanced']
                    m_prem = model_row['premature_point']
                    m_prem_lo = model_row['premature_lo']
                    m_prem_hi = model_row['premature_hi']
                    m_over = model_row['over_cautious_point']
                    m_over_lo = model_row['over_cautious_lo']
                    m_over_hi = model_row['over_cautious_hi']
                    m_total_error = m_prem + m_over
                    m_ce_e0 = model_row['ce_e0']
                    m_ce_e1 = model_row['ce_e1']
                    m_ce_e2 = model_row['ce_e2']
                    
                    print(f"    {model_name:<12} {m_ce:<8.3f} {m_ce_ref:<8.3f} {m_cce_bal:<10.3f} {m_prem:<8.3f}[{m_prem_lo:.3f},{m_prem_hi:.3f}] {m_over:<8.3f}[{m_over_lo:.3f},{m_over_hi:.3f}] {m_total_error:<12.3f} {m_ce_e0:<10.3f} {m_ce_e1:<10.3f} {m_ce_e2:<10.3f}")
    
    # Summary ranking
    print(f"\nRANKING BY CALIBRATION QUALITY:")
    cat_ce_pairs = [(cat, ce_vals[i]) for i, cat in enumerate(cats) if not np.isnan(ce_vals[i])]
    cat_ce_pairs.sort(key=lambda x: x[1])  # Sort by CE (lower is better)
    for rank, (cat, ce) in enumerate(cat_ce_pairs, 1):
        print(f"  {rank}. {cat}: CE = {ce:.3f}")
    
    ax.set_xticks(x); ax.set_xticklabels(cats)
    ax.set_ylabel('Rate')
    ax.set_ylim(0, 1)
    ax.set_title(f'R3-D: Calibration Error + Premature/Over-cautious (95% CI) by {group_by}')
    ax.legend()
    savefig(fig, outdir, 'fig_R3_D_calibration_rates')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', type=str, default='final_annotated_traces.jsonl')
    ap.add_argument('--outdir', type=str, default='figs_evidence')
    ap.add_argument('--n_boot', type=int, default=5000)
    ap.add_argument('--horizon', type=int, default=15, help='Horizon for A3–A4')
    ap.add_argument('--policy_threshold', type=str, default='high', choices=['high','medium'], help='Primary threshold E>=2; sensitivity E>=1')
    ap.add_argument('--group_by', type=str, default='category', choices=['category','model'], help='Aggregate by category (Base/Few-shot/RL Agents) or by model name')
    ap.add_argument('--ce_prevalence', type=str, default='global', choices=['global','group'], help='Use global or group-specific P(E) for CE computation')
    args = ap.parse_args()

    traces = load_traces(args.input)

    # Build turn-level df (A1/A2/A4)
    turn_df = build_turn_level_df(traces)

    # Report counts
    print('\n' + '='*80)
    print('R3 EVIDENCE STRENGTH ANALYSIS - DATA SUMMARY')
    print('='*80)
    print('Reporting checklist:')
    
    # Basic counts
    unique_trajectories = len({(t.get('dataset','Unknown'), t.get('question_id', t.get('id', None))) for t in traces})
    print(f"  N trajectories: {unique_trajectories}")
    print(f"  N turns (pre-answer): {len(turn_df)}")
    
    # Evidence level distribution
    prev_E = turn_df['E'].value_counts(normalize=True).sort_index().to_dict()
    print(f"  Prevalence of E levels: {prev_E}")
    
    
    # Model distribution
    model_counts = turn_df['category'].value_counts()
    print(f"  Model distribution: {dict(model_counts)}")
    
    # Dataset distribution
    dataset_counts = turn_df['dataset'].value_counts()
    print(f"  Dataset distribution: {dict(dataset_counts)}")
    
    # Answer event statistics
    answer_events = turn_df['answer_event'].sum()
    answer_rate = answer_events / len(turn_df)
    print(f"  Answer events: {answer_events} ({answer_rate:.1%} of turns)")
    
    # Correctness statistics (for answered events)
    answered_turns = turn_df[turn_df['answer_event'] == 1]
    if len(answered_turns) > 0:
        correct_answers = answered_turns['correct_event'].sum()
        overall_accuracy = correct_answers / len(answered_turns)
        print(f"  Overall accuracy: {correct_answers}/{len(answered_turns)} = {overall_accuracy:.1%}")
    
    print(f"  Bootstrap: {args.n_boot} resamples clustered by question")
    print(f"  Policy threshold: E >= {2 if args.policy_threshold == 'high' else 1}")
    print(f"  Horizon: {args.horizon} steps")
    print(f"  Evidence mode: cumulative (default)")

    ensure_dir(args.outdir)
    analyze_AB_combined(turn_df, args.outdir, n_boot=args.n_boot)
    traj_df = build_trajectory_level_df(traces, horizon=args.horizon)
    confusion_df = compute_confusion_data(traj_df, policy_threshold=args.policy_threshold, group_by=args.group_by)
    calib_df = compute_A4_calibration(turn_df, confusion_df, policy_threshold=args.policy_threshold, n_boot=args.n_boot, group_by=args.group_by, ce_prevalence=args.ce_prevalence)
    plot_A4_calibration(calib_df, turn_df, confusion_df, args.outdir, group_by=args.group_by, policy_threshold=args.policy_threshold, n_boot=args.n_boot, ce_prevalence=args.ce_prevalence)

    # Rigorous analysis: relationship between E and final answer correctness
    analyze_correctness_vs_E_rigorous(turn_df, args.outdir, n_boot=args.n_boot)

    # Final summary and interpretation guide
    print('\n' + '='*80)
    print('R3 ANALYSIS COMPLETE - INTERPRETATION GUIDE')
    print('='*80)
    
    print('\nSuggested figure captions:')
    print('Fig R3-D (Calibration & Rates): Overall calibration error and the split into Premature vs Over-cautious quantify each archetype\'s risk profile.')
    print('Fig R3-E (Timing): Agents that answer much before reaching High evidence exhibit premature behavior; better-calibrated agents wait.')
    
    print('\n' + '='*60)
    print('KEY INTERPRETATION GUIDELINES:')
    print('='*60)
    print('1. EVIDENCE LEVELS:')
    print('   - E=0 (Low): Insufficient information quality')
    print('   - E=1 (Medium): Sufficient quality but unclear')
    print('   - E=2 (High): Sufficient quality and clear')
    
    print('\n2. BEHAVIORAL PATTERNS:')
    print('   - PREMATURE: High answer rate at E=0, high FP rate')
    print('   - OVER-CAUTIOUS: Low answer rate at E=2, high FN rate')
    print('   - WELL-CALIBRATED: Low E=0 rate, high E=2 rate, balanced TP/TN')
    
    print('\n3. QUALITY INDICATORS:')
    print('   - Good models: High accuracy at E=2, low premature rate')
    print('   - Poor models: Low accuracy even at E=2, high premature rate')
    print('   - Timing efficiency: Large gap between "Not yet High" and "Already High" curves')
    
    print('\n4. CALIBRATION METRICS:')
    print('   - CE (Calibration Error): Lower is better (closer to ideal policy)')
    print('   - Premature Rate: Lower is better (fewer FP)')
    print('   - Over-cautious Rate: Lower is better (fewer FN)')
    print('   - Total Error Rate: Premature + Over-cautious (lower is better)')
    
    print('\n5. ACTIONABLE INSIGHTS:')
    print('   - High premature rate → Need better evidence thresholding')
    print('   - High over-cautious rate → Need more aggressive answering')
    print('   - Low accuracy at E=2 → Need better reasoning capabilities')
    print('   - Small timing gap → Need better evidence utilization')

    # Sensitivity analyses (brief hooks)
    # 1) Policy threshold E>=1
    if args.policy_threshold == 'high':
        print('\nSensitivity: Recomputing A3–A4 with policy E>=1 (should answer at Medium).')
        confusion_df_med = compute_confusion_data(traj_df, policy_threshold='medium', group_by=args.group_by)
        calib_df_med = compute_A4_calibration(turn_df, confusion_df_med, policy_threshold='medium', n_boot=args.n_boot)
        # Compare key rates to check for reversals
        def _summ(df):
            return {r['category']:{'CE':r['CE_point'],'Premature':r['premature_point'],'Over':r['over_cautious_point']} for _, r in df.iterrows()}
        print('  Primary rates:', _summ(calib_df))
        print('  Sensitivity rates:', _summ(calib_df_med))
        print('  Note: Report if any sensitivity reverses a conclusion; otherwise trends are robust.')


if __name__ == '__main__':
    main()