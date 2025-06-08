# -*- coding: utf-8 -*-
import numpy as np
import math
from omni_anomaly.spot import SPOT


def calc_point2point(predict, actual):
    """
    calculate f1 score by predict and actual.

    Args:
        predict (np.ndarray): the predict label
        actual (np.ndarray): np.ndarray
    """
    TP = np.sum(predict * actual)
    TN = np.sum((1 - predict) * (1 - actual))
    FP = np.sum(predict * (1 - actual))
    FN = np.sum((1 - predict) * actual)
    precision = TP / (TP + FP + 0.00001)
    recall = TP / (TP + FN + 0.00001)
    f1 = 2 * precision * recall / (precision + recall + 0.00001)
    return f1, precision, recall, TP, TN, FP, FN


def adjust_predicts(score, label,
                    threshold=None,
                    pred=None,
                    calc_latency=False):
    """
    Calculate adjusted predict labels using given `score`, `threshold` (or given `pred`) and `label`.

    Args:
        score (np.ndarray): The anomaly score
        label (np.ndarray): The ground-truth label
        threshold (float): The threshold of anomaly score.
            A point is labeled as "anomaly" if its score is lower than the threshold.
        pred (np.ndarray or None): if not None, adjust `pred` and ignore `score` and `threshold`,
        calc_latency (bool):

    Returns:
        np.ndarray: predict labels
    """
    if len(score) != len(label):
        raise ValueError("score and label must have the same length")
    score = np.asarray(score)
    label = np.asarray(label)
    latency = 0
    if pred is None:
        predict = score < threshold
    else:
        predict = pred
    actual = label > 0.1
    anomaly_state = False
    anomaly_count = 0
    for i in range(len(score)):
        if actual[i] and predict[i] and not anomaly_state:
                anomaly_state = True
                anomaly_count += 1
                for j in range(i, 0, -1):
                    if not actual[j]:
                        break
                    else:
                        if not predict[j]:
                            predict[j] = True
                            latency += 1
        elif not actual[i]:
            anomaly_state = False
        if anomaly_state:
            predict[i] = True
    if calc_latency:
        return predict, latency / (anomaly_count + 1e-4)
    else:
        return predict


def calc_seq(score, label, threshold, calc_latency=False):
    """
    Calculate f1 score for a score sequence
    """
    if calc_latency:
        predict, latency = adjust_predicts(score, label, threshold, calc_latency=calc_latency)
        t = list(calc_point2point(predict, label))
        t.append(latency)
        return t
    else:
        predict = adjust_predicts(score, label, threshold, calc_latency=calc_latency)
        return calc_point2point(predict, label)


def bf_search(score, label, start, end=None, step_num=1, display_freq=1, verbose=True):
    """
    Find the best-f1 score by searching best `threshold` in [`start`, `end`).


    Returns:
        list: list for results
        float: the `threshold` for best-f1
    """
    if step_num is None or end is None:
        end = start
        step_num = 1
    search_step, search_range, search_lower_bound = step_num, end - start, start
    if verbose:
        print("search range: ", search_lower_bound, search_lower_bound + search_range)
    threshold = search_lower_bound
    m = (-1., -1., -1.)
    m_t = 0.0
    for i in range(search_step):
        threshold += search_range / float(search_step)
        target = calc_seq(score, label, threshold, calc_latency=True)
        if target[0] > m[0]:
            m_t = threshold
            m = target
        if verbose and i % display_freq == 0:
            print("cur thr: ", threshold, target, m, m_t)
    print(m, m_t)
    return m, m_t


def parse_interpretation_label_file(label_file):
    segments = []
    with open(label_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or ':' not in line:
                continue
            seg, dims = line.split(':')
            start, end = map(int, seg.split('-'))
            dims = set(int(d) for d in dims.split(','))
            segments.append((start, end, dims))
    return segments


def compute_segment_ips(y_true, y_pred, feature_scores, segments, topk_percent=100):
    """
    计算分段（段级别）的IPS、TP、TN、FP、FN、Precision、Recall和F1指标。

    参数:
    ----------
    y_true : ndarray
        真实标签（shape: [时间步]）
    y_pred : ndarray
        预测标签（shape: [时间步]）
    feature_scores : ndarray
        模型预测的每个时间步每个维度的分数（shape: [时间步, 维度数]）
    segments : list of tuples
        每个段信息 (start, end, gt_dims)，
        其中 start 和 end 是该段的起止index（闭区间），gt_dims 是该段的真实异常维度（1-based索引的set）。
    topk_percent : int
        基于真实异常维度数量的百分比（100表示与真实异常维度数相同，150表示1.5倍）。

    返回:
    ----------
    results : list of dict
        每段的指标。
    summary : dict
        所有段的总体指标汇总。
    """
    results = []  # 存放每段的结果
    total_TP = total_TN = total_FP = total_FN = 0  # 统计总数
    total_ips = 0  # IPS加权累计
    total_weight = 0  # IPS加权的权重
    feature_dim = feature_scores.shape[1]  # 维度数

    # 遍历每个段
    for (start, end, gt_dims_raw) in segments:
        seg_true = y_true[start:end+1]  # 该段的真实标签（时间步级别）
        seg_pred = y_pred[start:end+1]  # 该段的预测标签（时间步级别）
        seg_scores = feature_scores[start:end+1]  # 该段的特征分数
        
        print(f"\n=== Debug Info ===")
        print(f"Segment: start={start}, end={end}")
        print(f"feature_dim: {feature_dim}")
        print(f"Raw gt_dims (1-based): {sorted(gt_dims_raw)}")

        # 修复：更严格的维度转换和验证
        gt_dims = set()
        for d in gt_dims_raw:
            # 确保维度在合理范围内
            if 1 <= d <= feature_dim:
                gt_dims.add(d - 1)  # 转换为0-based
            else:
                print(f"Warning: 维度 {d} 超出范围 [1, {feature_dim}]，已忽略")
        
        print(f"gt_dims (0-based): {sorted(gt_dims)}")
        print(f"gt_dims count: {len(gt_dims)}")

        # 找出段内被模型预测为异常的时间步索引（相对段内）
        detected_idxs = np.where(seg_pred == 1)[0]
        
        if len(detected_idxs) == 0:
            ips = 0
            TP = TN = FP = FN = 0
            inferred_dims = set()
            k = 0
        else:
            # 修改：基于真实异常维度数量计算k值
            if len(gt_dims) > 0:
                k = max(1, int(len(gt_dims) * topk_percent / 100))
                # 确保k不超过总维度数
                k = min(k, feature_dim)
            else:
                k = 1
            
            print(f"topk_percent: {topk_percent}%, gt_dims_count: {len(gt_dims)}, calculated k: {k}")
            
            inferred_dims = set()
            for idx in detected_idxs:
                scores = seg_scores[idx]
                
                # 获取top-k维度（分数最高的k个维度）
                if len(scores) > 0 and k > 0:
                    topk_dims = np.argsort(scores)[-k:]
                    # 确保所有推断维度都在有效范围内
                    topk_dims = [d for d in topk_dims if 0 <= d < feature_dim]
                    inferred_dims.update(topk_dims)
            
            # 计算交集和各项指标
            intersection = gt_dims & inferred_dims
            ips = len(intersection) / len(gt_dims) if len(gt_dims) > 0 else 0
            
            TP = len(intersection)
            FP = len(inferred_dims - gt_dims)
            FN = len(gt_dims - inferred_dims)
            
            # 计算TN：总维度数减去所有涉及的维度数
            union_dims = gt_dims.union(inferred_dims)
            TN = feature_dim - len(union_dims)
            TN = max(TN, 0)  # 确保TN不为负

        # Debug信息
        print(f"k (selected dimensions): {k}")
        print(f"inferred_dims (0-based): {sorted(inferred_dims)}")
        print(f"inferred_dims (1-based): {[d+1 for d in sorted(inferred_dims)]}")
        print(f"intersection: {sorted(intersection) if 'intersection' in locals() else 'N/A'}")
        print(f"TP: {TP}, FP: {FP}, FN: {FN}, TN: {TN}, IPS: {ips:.4f}")
        print("===================")

        seg_len = end - start + 1
        weight = seg_len
        
        total_TP += TP
        total_TN += TN
        total_FP += FP
        total_FN += FN
        total_ips += ips * weight
        total_weight += weight
        
        results.append({
            'start': start,
            'end': end,
            'TP': TP,
            'TN': TN,
            'FP': FP,
            'FN': FN,
            'IPS': ips,
            'k_selected': k,
            'gt_dims_count': len(gt_dims)
        })
    
    avg_ips = total_ips / total_weight if total_weight > 0 else 0
    precision = total_TP / (total_TP + total_FP) if (total_TP + total_FP) > 0 else 0
    recall = total_TP / (total_TP + total_FN) if (total_TP + total_FN) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    summary = {
        'TP': total_TP,
        'TN': total_TN,
        'FP': total_FP,
        'FN': total_FN,
        'IPS': avg_ips,
        'precision': precision,
        'recall': recall,
        'F1': f1
    }
    
    return results, summary


def pot_eval(init_score, score, label, q=1e-3, level=0.02, feature_scores=None, label_file=None, topk_percent=100):
    """
    Run POT method on given score, 并可选计算IPS与分段混淆矩阵.
    Args:
        init_score (np.ndarray): The data to get init threshold.
        score (np.ndarray): The data to run POT method.
        label: ground truth label
        q (float): Detection level (risk)
        level (float): Probability associated with the initial threshold t
        feature_scores (np.ndarray): (N, D) 每个点每个维度的异常分数
        label_file (str): interpretation_label 路径
        topk_percent (int): 取前百分之几的维度作为推断异常点位

    Returns:
        dict: pot result dict, 包含 segment_results 和 segment_summary（如有）
    """
    s = SPOT(q)  # SPOT object
    s.fit(init_score, score)  # data import
    s.initialize(level=level, min_extrema=True)  # initialization step
    ret = s.run(dynamic=False)  # run
    print(len(ret['alarms']))
    print(len(ret['thresholds']))
    pot_th = -np.mean(ret['thresholds'])
    pred, p_latency = adjust_predicts(score, label, pot_th, calc_latency=True)
    p_t = calc_point2point(pred, label)
    print('POT result: ', p_t, pot_th, p_latency)

    result = {
        'pot-f1': p_t[0],
        'pot-precision': p_t[1],
        'pot-recall': p_t[2],
        'pot-TP': p_t[3],
        'pot-TN': p_t[4],
        'pot-FP': p_t[5],
        'pot-FN': p_t[6],
        'pot-threshold': pot_th,
        'pot-latency': p_latency
    }

    # 新增：如有feature_scores和label_file则计算IPS与分段混淆
    if feature_scores is not None and label_file is not None:
        segments = parse_interpretation_label_file(label_file)
        segment_results, segment_summary = compute_segment_ips(
            y_true=label,
            y_pred=pred,
            feature_scores=feature_scores,
            segments=segments,
            topk_percent=topk_percent
        )
        result['segment_results'] = segment_results
        result['segment_summary'] = segment_summary

    return result
