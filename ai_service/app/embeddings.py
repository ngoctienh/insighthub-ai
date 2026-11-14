import logging
import os
import re
from typing import Tuple

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion
from sklearn.preprocessing import normalize

from .preprocessing import strip_vietnamese_diacritics

logger = logging.getLogger(__name__)

# Lightweight Vietnamese domain concept expansion used ONLY in local ML fallback
# to bridge common paraphrases (e.g., "thanh toán" vs "giao dịch", "tài xế" vs "shipper")
# without modifying user-facing text.
_CONCEPT_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(giao dịch|trả tiền|quẹt thẻ|chuyển khoản|ví điện tử|momo|zalopay|vnpay|thẻ tín dụng|thẻ atm)\b", re.I), "concept_payment"),
    (re.compile(r"\b(thanh toán|checkout|payment)\b", re.I), "concept_payment"),
    (re.compile(r"\b(shipper|tài xế|người giao|shiper|driver)\b", re.I), "concept_driver"),
    (re.compile(r"\b(giao hàng|giao đồ|vận chuyển|ship|đơn giao|thời gian giao)\b", re.I), "concept_delivery"),
    (re.compile(r"\b(muộn|trễ|chậm|quá lâu|trễ hẹn|không chính xác)\b", re.I), "concept_delay"),
    (re.compile(r"\b(thông báo|push|notification|tin nhắn báo|chuông báo|không báo)\b", re.I), "concept_notification"),
    (re.compile(r"\b(mã giảm giá|voucher|khuyến mãi|promo|coupon|ưu đãi|giảm giá)\b", re.I), "concept_voucher"),
    (re.compile(r"\b(đăng nhập|login|otp|mật khẩu|xác thực|tài khoản|session)\b", re.I), "concept_auth"),
    (re.compile(r"\b(tìm kiếm|search|lọc món|bộ lọc|filter|kết quả tìm)\b", re.I), "concept_search"),
    (re.compile(r"\b(định vị|gps|bản đồ|vị trí|địa chỉ|map)\b", re.I), "concept_location"),
    (re.compile(r"\b(treo app|đứng máy|crash|văng app|thoát đột ngột|lag|đơ)\b", re.I), "concept_crash"),
    (re.compile(r"\b(thực đơn|menu|giỏ hàng|cart|đặt món)\b", re.I), "concept_menu_cart"),
]


class _FieldExtractor(BaseEstimator, TransformerMixin):
    def __init__(self, key: str):
        self.key = key

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return [item[self.key] for item in X]


def _prepare_record(text: str) -> dict[str, str]:
    lowered = text.lower()
    concepts: list[str] = []
    for pattern, tag in _CONCEPT_MAP:
        hits = pattern.findall(lowered)
        if hits:
            concepts.extend([tag] * min(3, len(hits)))
    return {
        "word": lowered,
        "unaccented": strip_vietnamese_diacritics(lowered),
        "concepts": " ".join(concepts) if concepts else "concept_general",
    }


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    if vectors.size == 0:
        return vectors
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    return (vectors / norms).astype(np.float32)


def _generate_openai_embeddings(texts: list[str]) -> Tuple[np.ndarray, str]:
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip()
    client = OpenAI(api_key=api_key, timeout=30.0)

    vectors: list[list[float]] = []
    batch_size = 64
    for start in range(0, len(texts), batch_size):
        batch = [t if t.strip() else "empty feedback" for t in texts[start : start + batch_size]]
        resp = client.embeddings.create(model=model, input=batch)
        for item in resp.data:
            vectors.append(item.embedding)

    arr = np.asarray(vectors, dtype=np.float32)
    return _l2_normalize(arr), f"openai:{model}"


def _generate_local_embeddings(texts: list[str]) -> Tuple[np.ndarray, str]:
    if not texts:
        return np.zeros((0, 1), dtype=np.float32), "local_ml:tfidf-svd-v1"

    records = [_prepare_record(t if t.strip() else "empty") for t in texts]

    from sklearn.pipeline import Pipeline

    union = FeatureUnion(
        transformer_list=[
            (
                "word",
                Pipeline([
                    ("extract", _FieldExtractor("word")),
                    (
                        "tfidf",
                        TfidfVectorizer(
                            ngram_range=(1, 2),
                            min_df=1,
                            max_features=800,
                            sublinear_tf=True,
                            token_pattern=r"(?u)\b[a-zA-ZÀ-ỹ0-9_]{2,}\b",
                        ),
                    ),
                ]),
            ),
            (
                "concepts",
                Pipeline([
                    ("extract", _FieldExtractor("concepts")),
                    (
                        "tfidf",
                        TfidfVectorizer(
                            min_df=1,
                            token_pattern=r"concept_\w+",
                        ),
                    ),
                ]),
            ),
            (
                "char",
                Pipeline([
                    ("extract", _FieldExtractor("unaccented")),
                    (
                        "tfidf",
                        TfidfVectorizer(
                            analyzer="char_wb",
                            ngram_range=(3, 5),
                            min_df=1,
                            max_features=600,
                            sublinear_tf=True,
                        ),
                    ),
                ]),
            ),
        ],
        transformer_weights={"word": 1.35, "concepts": 1.45, "char": 0.45},
    )
    sparse_matrix = union.fit_transform(records)

    n_samples, n_features = sparse_matrix.shape
    if n_samples >= 20 and n_features >= 16:
        n_components = min(128, n_samples - 1, n_features - 1)
        svd = TruncatedSVD(n_components=n_components, random_state=42)
        dense = svd.fit_transform(sparse_matrix)
        dense = normalize(dense, norm="l2", axis=1)
        return dense.astype(np.float32), "local_ml:tfidf-svd-v1"

    dense = sparse_matrix.toarray().astype(np.float32)
    return _l2_normalize(dense), "local_ml:tfidf-v1"


def generate_embeddings(texts: list[str], use_llm: bool = True) -> Tuple[np.ndarray, str]:
    """Generate L2-normalized dense embeddings via OpenAI or local multilingual TF-IDF+SVD."""
    provider = os.getenv("AI_PROVIDER", "auto").strip().lower()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    if use_llm and openai_key and provider in ("auto", "openai"):
        try:
            return _generate_openai_embeddings(texts)
        except Exception as exc:
            logger.warning("OpenAI embedding failed, falling back to local ML embeddings: %s", exc)

    return _generate_local_embeddings(texts)
