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


def compute_segment_ips(y_true, y_pred, feature_scores, interpretation_segments, topk_percent=100):
    """
    计算基于 y_true 异常段的 IPS、TP、TN、FP、FN、Precision、Recall 和 F1 指标，
    真实异常维度按照 interpretation_segments 的顺序依次匹配。

    参数:
    ----------
    y_true : ndarray
        真实标签（shape: [时间步]）
    y_pred : ndarray
        预测标签（shape: [时间步]）
    feature_scores : ndarray
        模型预测的每个时间步每个维度的分数（shape: [时间步, 维度数]）
    interpretation_segments : list of tuples
        interpretation_label 文件中的段信息 (start, end, gt_dims)，
        其中 start 和 end 是该段的起止索引（闭区间），gt_dims 是该段的真实异常维度（1-based索引的 set）。
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

    # 计算 y_true 中的异常段
    anomaly_segments = []
    in_anomaly = False
    start_idx = 0
    for i, val in enumerate(y_true):
        if val > 0 and not in_anomaly:
            in_anomaly = True
            start_idx = i
        elif val == 0 and in_anomaly:
            in_anomaly = False
            anomaly_segments.append((start_idx, i - 1))
    if in_anomaly:  # 如果最后一个点是异常
        anomaly_segments.append((start_idx, len(y_true) - 1))

    print("\n=== 全局调试信息 ===")
    print(f"y_true shape: {y_true.shape}, unique values: {np.unique(y_true)}")
    print(f"y_pred shape: {y_pred.shape}, unique values: {np.unique(y_pred)}")
    print(f"feature_scores shape: {feature_scores.shape}")
    print(f"y_true 中的异常段: {anomaly_segments}\n")

    # 按顺序匹配 interpretation_segments 的异常维度
    for i, (start, end) in enumerate(anomaly_segments):
        print(f"\n=== 处理第 {i + 1}/{len(anomaly_segments)} 段 ===")
        print(f"段范围: start={start}, end={end}")

        seg_true = y_true[start:end + 1]
        seg_pred = y_pred[start:end + 1]
        seg_scores = feature_scores[start:end + 1]

        print(f"段内真实标签 (seg_true): {seg_true}")
        print(f"段内预测标签 (seg_pred): {seg_pred}")
        print(f"段内真实异常时间点索引 (相对段内): {np.where(seg_true > 0)[0]}")
        print(f"段内是否有预测为异常的时间点: {np.any(seg_pred)}")

        # 获取 interpretation_segments 中的异常维度
        gt_dims = set()
        if i < len(interpretation_segments):
            _, _, dims = interpretation_segments[i]
            gt_dims.update(dims)
        gt_dims = {d - 1 for d in gt_dims if 1 <= d <= feature_dim}  # 转为 0-based 索引
        print(f"真实异常维度 (0-based): {sorted(gt_dims)}")

        detected_idxs = np.where(seg_pred)[0]
        print(f"段内检测到的异常时间点索引 (相对段内): {detected_idxs}")

        if len(detected_idxs) == 0:
            print("未检测到任何异常点，将整个段中的时间索引标记为异常")
            detected_idxs = np.arange(len(seg_scores))  # 将整个段的时间索引标记为异常

            inferred_dims = set()
            for idx in detected_idxs:
                scores = seg_scores[idx]
                k = max(1, int(len(gt_dims) * topk_percent / 100))
                k = min(k, feature_dim)
                topk_dims = np.argsort(scores)[-k:]
                inferred_dims.update(topk_dims)

            intersection = gt_dims & inferred_dims
            ips = len(intersection) / len(gt_dims) if len(gt_dims) > 0 else 0
            TP = len(intersection)
            FP = len(inferred_dims - gt_dims)
            FN = len(gt_dims - inferred_dims)
            TN = feature_dim - len(gt_dims.union(inferred_dims))
        else:
            k = max(1, int(len(gt_dims) * topk_percent / 100))
            k = min(k, feature_dim)

            inferred_dims = set()
            for idx in detected_idxs:
                scores = seg_scores[idx]
                topk_dims = np.argsort(scores)[-k:]
                inferred_dims.update(topk_dims)

            intersection = gt_dims & inferred_dims
            ips = len(intersection) / len(gt_dims) if len(gt_dims) > 0 else 0
            TP = len(intersection)
            FP = len(inferred_dims - gt_dims)
            FN = len(gt_dims - inferred_dims)
            TN = feature_dim - len(gt_dims.union(inferred_dims))

        print(f"推断的异常维度 (0-based): {sorted(inferred_dims)}")
        print(f"真实与推断的交集: {sorted(intersection) if 'intersection' in locals() else 'N/A'}")
        print(f"段内指标: TP={TP}, FP={FP}, FN={FN}, TN={TN}, IPS={ips:.4f}")

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

    print("\n=== 汇总指标 ===")
    print(f"总 TP: {total_TP}, 总 TN: {total_TN}, 总 FP: {total_FP}, 总 FN: {total_FN}")
    print(f"平均 IPS: {avg_ips:.4f}, Precision: {precision:.4f}, Recall: {recall:.4f}, F1: {f1:.4f}")

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
    if len(init_score) == 0 or len(score) == 0:
        print("警告：init_score 或 score 为空，无法运行 POT 方法。")
        return {}

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
            interpretation_segments=segments,
            topk_percent=topk_percent
        )
        result['segment_results'] = segment_results
        result['segment_summary'] = segment_summary

    return result
