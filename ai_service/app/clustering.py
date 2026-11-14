from typing import Any

import numpy as np
from sklearn.cluster import DBSCAN

from .schemas import ClusterMember, FeedbackInput, SimilarityPair


def cosine_similarity_matrix(vectors: np.ndarray) -> np.ndarray:
    """
    Compute exact cosine similarity matrix:
    similarity(A, B) = (A . B) / (||A|| * ||B||)
    """
    if vectors.size == 0:
        return np.zeros((0, 0), dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    safe_norms = np.where(norms == 0.0, 1.0, norms)
    unit_vectors = vectors / safe_norms
    sim = np.matmul(unit_vectors, unit_vectors.T)
    return np.clip(sim, -1.0, 1.0)


def find_duplicate_candidates(
    feedbacks: list[FeedbackInput],
    sim_matrix: np.ndarray,
    text_hashes: list[str],
    threshold: float,
) -> list[SimilarityPair]:
    """Return high-similarity feedback pairs as human-reviewable duplicate candidates."""
    n = len(feedbacks)
    candidates: list[SimilarityPair] = []
    for i in range(n):
        for j in range(i + 1, n):
            score = float(sim_matrix[i, j])
            exact_match = text_hashes[i] == text_hashes[j]
            if exact_match or score >= threshold:
                candidates.append(
                    SimilarityPair(
                        feedback_a_id=feedbacks[i].id,
                        feedback_b_id=feedbacks[j].id,
                        similarity_score=round(max(score, 1.0 if exact_match else score), 4),
                        is_exact_normalized_match=exact_match,
                    )
                )
    candidates.sort(key=lambda item: item.similarity_score, reverse=True)
    return candidates


def cluster_feedbacks_dbscan(
    feedbacks: list[FeedbackInput],
    vectors: np.ndarray,
    sim_matrix: np.ndarray,
    eps: float = 0.48,
    min_samples: int = 2,
) -> tuple[list[dict[str, Any]], list[int]]:
    """
    Run DBSCAN over cosine distance matrix (1 - cosine_similarity).
    Returns (clusters_with_members, unassigned_noise_feedback_ids).
    """
    n = len(feedbacks)
    if n == 0:
        return [], []
    if n == 1:
        return [], [feedbacks[0].id]

    distance_matrix = np.clip(1.0 - sim_matrix, 0.0, 2.0)
    np.fill_diagonal(distance_matrix, 0.0)

    model = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
    labels = model.fit_predict(distance_matrix)

    grouped_indices: dict[int, list[int]] = {}
    unassigned_ids: list[int] = []
    for idx, label in enumerate(labels):
        if int(label) == -1:
            unassigned_ids.append(feedbacks[idx].id)
        else:
            grouped_indices.setdefault(int(label), []).append(idx)

    clusters: list[dict[str, Any]] = []
    for cluster_idx, member_indices in enumerate(grouped_indices.values()):
        member_vectors = vectors[member_indices]
        centroid = np.mean(member_vectors, axis=0, keepdims=True)
        centroid_norm = np.linalg.norm(centroid)
        if centroid_norm > 0:
            centroid = centroid / centroid_norm

        members: list[ClusterMember] = []
        for idx in member_indices:
            vec = vectors[idx : idx + 1]
            vec_norm = np.linalg.norm(vec)
            if vec_norm > 0 and centroid_norm > 0:
                sim = float(np.matmul(vec / vec_norm, centroid.T)[0, 0])
            else:
                sim = 0.0
            members.append(
                ClusterMember(
                    feedback_id=feedbacks[idx].id,
                    similarity_to_centroid=round(max(0.0, min(1.0, sim)), 4),
                )
            )
        members.sort(key=lambda m: m.similarity_to_centroid, reverse=True)
        clusters.append(
            {
                "cluster_index": cluster_idx,
                "member_indices": member_indices,
                "members": members,
            }
        )

    clusters.sort(key=lambda c: len(c["members"]), reverse=True)
    for new_idx, cluster in enumerate(clusters):
        cluster["cluster_index"] = new_idx

    return clusters, unassigned_ids
