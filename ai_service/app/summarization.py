import json
import logging
import os
import re
from collections import Counter
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer

from .preprocessing import clean_text
from .schemas import FeedbackInput, ReplyTone

logger = logging.getLogger(__name__)

_VIETNAMESE_STOPWORDS = {
    "và", "là", "của", "cho", "khi", "đã", "đang", "bị", "với", "trong", "không",
    "được", "này", "đó", "nhưng", "vì", "nên", "mà", "thì", "tôi", "mình", "bạn",
    "ứng", "dụng", "app", "rất", "quá", "lại", "có", "thể", "cần", "nếu", "hay",
    "nhiều", "một", "các", "những", "về", "từ", "đến", "lúc", "sau", "trước",
    "rồi", "vẫn", "chưa", "hơn", "nhất", "cũng", "để", "làm", "ra", "vào", "lên",
    "xuống", "qua", "trên", "dưới", "theo", "như", "xin", "vui", "lòng", "giúp",
}


def _extract_top_phrases(cluster_texts: list[str], top_k: int = 4) -> list[str]:
    if not cluster_texts:
        return []
    try:
        vec = TfidfVectorizer(
            ngram_range=(1, 3),
            max_features=40,
            token_pattern=r"(?u)\b[a-zA-ZÀ-ỹ]{2,}\b",
        )
        mat = vec.fit_transform(cluster_texts)
        scores = mat.mean(axis=0).A1
        vocab = vec.get_feature_names_out()
        ranked = sorted(zip(vocab, scores), key=lambda x: x[1], reverse=True)
        selected: list[str] = []
        for phrase, _ in ranked:
            tokens = phrase.lower().split()
            if all(t in _VIETNAMESE_STOPWORDS for t in tokens):
                continue
            if any(phrase in existing or existing in phrase for existing in selected):
                continue
            selected.append(phrase)
            if len(selected) >= top_k:
                break
        return selected
    except Exception:
        return []


_SOURCE_LABELS = {
    "WEB_FORM": "Form Web",
    "EMAIL": "Email",
    "LIVE_CHAT": "Live Chat",
    "COMMUNITY": "Cộng đồng",
}


def _analyze_symptoms_and_domain(feedbacks: list[FeedbackInput]) -> dict[str, Any]:
    joined = " ".join(clean_text(f"{fb.title} {fb.content}").lower() for fb in feedbacks)
    sources = Counter(fb.source_code for fb in feedbacks)
    top_source_code = sources.most_common(1)[0][0] if sources else "WEB_FORM"
    top_source = _SOURCE_LABELS.get(top_source_code, top_source_code)

    rules = [
        (
            r"thanh toán|giao dịch|thẻ|ví|momo|zalopay|vnpay|trừ tiền|checkout",
            "Lỗi & trục trặc quy trình thanh toán đơn hàng",
            [
                "Giả thuyết cần kiểm tra: kết nối với cổng thanh toán (thẻ/ví điện tử) có thể bị timeout hoặc trả mã lỗi chưa được xử lý mượt.",
                "Giả thuyết cần kiểm tra: trạng thái đồng bộ giữa giao dịch đã trừ tiền và trạng thái đơn hàng trên hệ thống chưa nhất quán.",
            ],
            "Người dùng không thể hoàn tất đặt món hoặc lo ngại bị trừ tiền nhưng đơn chưa được xác nhận, ảnh hưởng trực tiếp tới tỷ lệ chuyển đổi.",
            [
                "Kiểm tra log giao dịch thất bại và cơ chế retry/idempotency tại bước xác nhận thanh toán.",
                "Bổ sung thông báo trạng thái rõ ràng và cơ chế hoàn/đối soát tự động khi cổng thanh toán phản hồi chậm.",
            ],
        ),
        (
            r"giao hàng|tài xế|shipper|muộn|chậm|trễ|thời gian dự kiến|đến lâu",
            "Giao hàng chậm và sai lệch thời gian dự kiến",
            [
                "Giả thuyết cần kiểm tra: thuật toán ước tính thời gian giao hàng (ETA) có thể chưa phản ánh đúng tình trạng kẹt xe hoặc tải đơn giờ cao điểm.",
                "Giả thuyết cần kiểm tra: quá trình điều phối và ghép đơn cho tài xế ở một số khu vực có thể đang bị trễ.",
            ],
            "Khách hàng phải chờ lâu hơn thời gian hiển thị trên app, dẫn đến giảm trải nghiệm nhận đồ ăn nóng và tăng nguy cơ hủy đơn.",
            [
                "Hiệu chỉnh mô hình ước lượng ETA theo khung giờ cao điểm và mật độ tài xế thực tế.",
                "Gửi cảnh báo chủ động kèm lý do minh bạch khi đơn có nguy cơ trễ so với dự kiến.",
            ],
        ),
        (
            r"thông báo|push|notification|không báo|chuông|tin nhắn báo",
            "Thiếu hoặc chậm thông báo trạng thái đơn hàng",
            [
                "Giả thuyết cần kiểm tra: dịch vụ gửi push notification (FCM/APNs) hoặc cấu hình quyền thông báo trên một số phiên bản thiết bị có thể bị gián đoạn.",
                "Giả thuyết cần kiểm tra: sự kiện cập nhật trạng thái từ tài xế/quán ăn có thể chưa kích hoạt kịp thời luồng gửi thông báo.",
            ],
            "Người dùng bỏ lỡ thời điểm tài xế đến giao hoặc không nắm được tiến độ đơn hàng nếu không tự mở lại ứng dụng.",
            [
                "Rà soát tỷ lệ gửi thành công push notification theo từng nền tảng iOS/Android và bổ sung fallback thông báo trong ứng dụng.",
                "Bổ sung tùy chọn nhắc nhận hàng khi tài xế vào bán kính gần điểm giao.",
            ],
        ),
        (
            r"voucher|mã giảm giá|khuyến mãi|ưu đãi|giảm giá|coupon",
            "Khó khăn khi áp dụng mã giảm giá và khuyến mãi",
            [
                "Giả thuyết cần kiểm tra: điều kiện áp dụng voucher (giá trị tối thiểu, khung giờ, phương thức thanh toán) có thể chưa hiển thị rõ trước khi bấm áp dụng.",
                "Giả thuyết cần kiểm tra: logic kiểm tra hợp lệ mã khuyến mãi tại màn hình giỏ hàng có thể phát sinh xung đột khi thay đổi món.",
            ],
            "Khách hàng mất thời gian thử nhiều mã hoặc bỏ dở đơn hàng khi mức giảm không khớp kỳ vọng.",
            [
                "Hiển thị trực quan lý do cụ thể khi mã không đủ điều kiện và tự động gợi ý mã hợp lệ tốt nhất.",
                "Kiểm tra lại luồng tính toán lại khuyến mãi khi cập nhật giỏ hàng.",
            ],
        ),
        (
            r"định vị|gps|bản đồ|vị trí|địa chỉ|tìm kiếm|lọc",
            "Sai lệch định vị địa chỉ và bất tiện khi tìm kiếm món",
            [
                "Giả thuyết cần kiểm tra: bộ giải mã địa chỉ/GPS có thể chưa chính xác ở khu vực nhiều hẻm hoặc chung cư.",
                "Giả thuyết cần kiểm tra: chỉ mục tìm kiếm/bộ lọc món ăn và quán theo khoảng cách cần tối ưu độ liên quan.",
            ],
            "Người dùng phải nhập lại địa chỉ nhiều lần hoặc mất nhiều thao tác để tìm đúng quán và món mong muốn.",
            [
                "Cho phép ghim chính xác điểm giao trên bản đồ kèm ghi chú cổng/tòa nhà quen thuộc.",
                "Cải thiện tìm kiếm tiếng Việt không dấu/gợi ý theo lịch sử đặt món và bộ lọc nhanh.",
            ],
        ),
        (
            r"treo|crash|văng|lag|chậm|đứng máy|hiệu năng|tải lâu",
            "Ứng dụng phản hồi chậm, giật lag hoặc thoát đột ngột",
            [
                "Giả thuyết cần kiểm tra: việc tải nhiều hình ảnh thực đơn độ phân giải cao cùng lúc hoặc tràn bộ nhớ có thể làm thiết bị cấu hình trung bình bị chậm.",
                "Giả thuyết cần kiểm tra: một số màn hình chưa có cơ chế tải từng phần (lazy-load) khi mạng yếu.",
            ],
            "Trải nghiệm duyệt thực đơn và thao tác đặt món bị gián đoạn, gây khó chịu cho người dùng trên thiết bị di động.",
            [
                "Tối ưu kích thước ảnh, lưu đệm (cache) dữ liệu thực đơn và áp dụng phân trang, tải từng phần.",
                "Thu thập nhật ký lỗi ứng dụng (crash log) theo phiên bản và hệ điều hành để khoanh vùng điểm nghẽn.",
            ],
        ),
    ]

    for pattern, theme_title, causes, impact, recs in rules:
        if re.search(pattern, joined):
            return {
                "theme_title": theme_title,
                "causes": causes,
                "impact": impact,
                "recommendations": recs,
                "top_source": top_source,
            }

    return {
        "theme_title": "",
        "causes": [
            "Giả thuyết cần kiểm tra: các phản hồi cho thấy điểm ma sát lặp lại ở luồng thao tác được nhắc tới; cần đối chiếu log hệ thống trước khi kết luận nguyên nhân gốc.",
        ],
        "impact": "Ảnh hưởng trực tiếp đến sự hài lòng và tính mượt mà khi khách hàng sử dụng tính năng liên quan.",
        "recommendations": [
            "Phỏng vấn nhanh hoặc phản hồi lại nhóm khách hàng đã gửi ý kiến để tái hiện chính xác ngữ cảnh phát sinh.",
            "Rà soát thiết kế UX và log API liên quan để lên phương án cải tiến phù hợp.",
        ],
        "top_source": top_source,
    }


def _local_summarize(
    feedbacks: list[FeedbackInput],
    representative_ids: list[int] | None = None,
    custom_title: str | None = None,
) -> dict[str, Any]:
    cleaned_texts = [clean_text(f"{fb.title}. {fb.content}") for fb in feedbacks]
    phrases = _extract_top_phrases(cleaned_texts, top_k=3)
    analysis = _analyze_symptoms_and_domain(feedbacks)

    if custom_title and custom_title.strip():
        title = custom_title.strip()
    elif analysis["theme_title"]:
        title = analysis["theme_title"]
    elif phrases:
        title = "Vấn đề liên quan đến " + ", ".join(phrases[:2]).capitalize()
    else:
        title = clean_text(feedbacks[0].title)[:90]

    by_id = {fb.id: fb for fb in feedbacks}
    ordered = (
        [by_id[fid] for fid in representative_ids if fid in by_id]
        if representative_ids
        else feedbacks
    )
    snippets = [clean_text(fb.title) for fb in ordered[:3] if clean_text(fb.title)]
    if len(feedbacks) == 1:
        fb = feedbacks[0]
        clean_content = clean_text(fb.content)
        short_content = clean_content[:180] + ("..." if len(clean_content) > 180 else "")
        summary = f"[{fb.impact_level}] {clean_text(fb.title)} — {short_content}"
        if phrases:
            summary += f" (Từ khóa: {', '.join(phrases)})"
    else:
        summary = (
            f"Nhóm gồm {len(feedbacks)} phản hồi tương đồng (chủ yếu qua {analysis['top_source']}), "
            f"tập trung vào vấn đề: {'; '.join(snippets)}."
        )
        if phrases:
            summary += f" Cụm từ nổi bật ghi nhận từ người dùng: {', '.join(phrases)}."

    draft_reply = build_local_draft_reply(title, summary, tone="empathetic")

    return {
        "title": title,
        "summary": summary,
        "possible_causes": analysis["causes"],
        "user_impact": analysis["impact"],
        "ai_recommendations": analysis["recommendations"],
        "draft_customer_reply": draft_reply,
        "analysis_mode": "local_nlp",
        "ai_confidence": round(min(0.92, 0.65 + 0.04 * len(feedbacks)), 2),
    }


def build_local_draft_reply(title: str, summary: str, tone: ReplyTone = "empathetic") -> str:
    if tone == "resolved":
        return (
            f"Chào bạn,\n\n"
            f"Cảm ơn bạn đã đóng góp ý kiến liên quan đến vấn đề \"{title}\". "
            f"Đội ngũ sản phẩm của chúng tôi đã tiếp nhận, xử lý và cập nhật bản cải tiến cho nội dung này.\n\n"
            f"Bạn vui lòng cập nhật phiên bản mới nhất hoặc kiểm tra lại trải nghiệm nhé. "
            f"Nếu vẫn gặp bất kỳ bất tiện nào, hãy phản hồi ngay để chúng tôi hỗ trợ kịp thời!\n\n"
            f"Trân trọng,\nĐội ngũ Sản phẩm InsightHub"
        )
    if tone == "update":
        return (
            f"Chào bạn,\n\n"
            f"Cảm ơn bạn đã chia sẻ phản hồi về \"{title}\". "
            f"Chúng tôi đã tổng hợp ý kiến của bạn cùng các phản hồi tương tự để đưa vào lộ trình phân tích và ưu tiên xử lý.\n\n"
            f"Chúng tôi sẽ gửi thông báo cập nhật ngay khi có tiến triển mới trên Product Roadmap.\n\n"
            f"Trân trọng,\nĐội ngũ Sản phẩm InsightHub"
        )
    return (
        f"Chào bạn,\n\n"
        f"Rất cảm ơn bạn đã dành thời gian phản hồi về tình trạng \"{title}\". "
        f"Chúng tôi thành thật xin lỗi vì sự bất tiện mà trải nghiệm này có thể đã gây ra cho bạn.\n\n"
        f"Phản hồi của bạn đã được ghi nhận vào hệ thống phân tích của đội ngũ Product để kiểm tra kỹ hơn các trường hợp tương tự "
        f"và ưu tiên phương án khắc phục sớm nhất.\n\n"
        f"Trân trọng,\nĐội ngũ Chăm sóc Khách hàng & Sản phẩm"
    )


def _build_llm_prompt(feedbacks: list[FeedbackInput]) -> str:
    lines = []
    for idx, fb in enumerate(feedbacks[:12], start=1):
        lines.append(
            f"{idx}. [{fb.source_code} | Impact={fb.impact_level}] {clean_text(fb.title)}: {clean_text(fb.content)}"
        )
    feedback_block = "\n".join(lines)
    return (
        "Bạn là AI Product Discovery Assistant. Hãy phân tích nhóm feedback tiếng Việt sau và trả về DUY NHẤT JSON hợp lệ.\n"
        "QUY TẮC NGHIÊM NGẶT:\n"
        "- Chỉ dựa trên nội dung feedback bên dưới.\n"
        "- Không khẳng định nguyên nhân kỹ thuật nội bộ như sự thật chắc chắn; luôn nêu ở dạng giả thuyết cần kiểm tra.\n"
        "- Trả về JSON với đúng các khóa: "
        "title (string ngắn gọn), summary (string 2-3 câu), "
        "possible_causes (array of 2-3 strings giả thuyết), "
        "user_impact (string), "
        "ai_recommendations (array of 2-3 strings đề xuất cải tiến), "
        "draft_customer_reply (string thư phản hồi lịch sự bằng tiếng Việt), "
        "ai_confidence (number 0..1).\n\n"
        f"Danh sách feedback ({len(feedbacks)} mục):\n{feedback_block}"
    )


def _parse_json_payload(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.DOTALL).strip()
    return json.loads(cleaned)


def summarize_cluster(
    feedbacks: list[FeedbackInput],
    representative_ids: list[int] | None = None,
    use_llm: bool = True,
    custom_title: str | None = None,
) -> dict[str, Any]:
    """Summarize cluster using OpenAI / Claude if configured, otherwise grounded local NLP."""
    if not feedbacks:
        return {
            "title": custom_title or "Nhóm Insight trống",
            "summary": "Chưa có feedback trong nhóm.",
            "possible_causes": [],
            "user_impact": "Chưa xác định.",
            "ai_recommendations": [],
            "draft_customer_reply": "",
            "analysis_mode": "local_nlp",
            "ai_confidence": 0.0,
        }

    provider = os.getenv("AI_PROVIDER", "auto").strip().lower()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

    if use_llm and openai_key and provider in ("auto", "openai"):
        try:
            from openai import OpenAI

            client = OpenAI(api_key=openai_key, timeout=30.0)
            model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini").strip()
            resp = client.chat.completions.create(
                model=model,
                response_format={"type": "json_object"},
                temperature=0.2,
                messages=[
                    {"role": "system", "content": "Bạn là trợ lý phân tích Product Feedback chuẩn xác, không bịa đặt."},
                    {"role": "user", "content": _build_llm_prompt(feedbacks)},
                ],
            )
            data = _parse_json_payload(resp.choices[0].message.content or "{}")
            return {
                "title": (custom_title or data.get("title") or feedbacks[0].title)[:160],
                "summary": str(data.get("summary") or ""),
                "possible_causes": [str(x) for x in data.get("possible_causes", [])][:4],
                "user_impact": str(data.get("user_impact") or ""),
                "ai_recommendations": [str(x) for x in data.get("ai_recommendations", [])][:4],
                "draft_customer_reply": str(data.get("draft_customer_reply") or ""),
                "analysis_mode": "openai",
                "ai_confidence": float(data.get("ai_confidence") or 0.85),
            }
        except Exception as exc:
            logger.warning("OpenAI summarization failed, falling back: %s", exc)

    if use_llm and anthropic_key and provider in ("auto", "anthropic"):
        try:
            from anthropic import Anthropic

            client = Anthropic(api_key=anthropic_key, timeout=30.0)
            model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest").strip()
            resp = client.messages.create(
                model=model,
                max_tokens=900,
                temperature=0.2,
                messages=[{"role": "user", "content": _build_llm_prompt(feedbacks)}],
            )
            text_out = resp.content[0].text if resp.content else "{}"
            data = _parse_json_payload(text_out)
            return {
                "title": (custom_title or data.get("title") or feedbacks[0].title)[:160],
                "summary": str(data.get("summary") or ""),
                "possible_causes": [str(x) for x in data.get("possible_causes", [])][:4],
                "user_impact": str(data.get("user_impact") or ""),
                "ai_recommendations": [str(x) for x in data.get("ai_recommendations", [])][:4],
                "draft_customer_reply": str(data.get("draft_customer_reply") or ""),
                "analysis_mode": "anthropic",
                "ai_confidence": float(data.get("ai_confidence") or 0.85),
            }
        except Exception as exc:
            logger.warning("Anthropic summarization failed, falling back: %s", exc)

    return _local_summarize(feedbacks, representative_ids=representative_ids, custom_title=custom_title)


def generate_draft_reply(
    insight_title: str,
    insight_summary: str,
    sample_feedbacks: list[str],
    tone: ReplyTone = "empathetic",
    use_llm: bool = True,
) -> tuple[str, str]:
    provider = os.getenv("AI_PROVIDER", "auto").strip().lower()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

    prompt = (
        f"Viết một email phản hồi khách hàng bằng tiếng Việt lịch sự, chân thành (tone={tone}) "
        f"về vấn đề '{insight_title}'. Tóm tắt insight: {insight_summary}. "
        f"Một số ý kiến khách hàng: {' | '.join(sample_feedbacks[:4])}. "
        "Không hứa hẹn mốc ngày cụ thể không có trong dữ liệu."
    )

    if use_llm and openai_key and provider in ("auto", "openai"):
        try:
            from openai import OpenAI

            client = OpenAI(api_key=openai_key, timeout=25.0)
            resp = client.chat.completions.create(
                model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini").strip(),
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            return (resp.choices[0].message.content or "").strip(), "openai"
        except Exception as exc:
            logger.warning("OpenAI draft reply failed: %s", exc)

    if use_llm and anthropic_key and provider in ("auto", "anthropic"):
        try:
            from anthropic import Anthropic

            client = Anthropic(api_key=anthropic_key, timeout=25.0)
            resp = client.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest").strip(),
                max_tokens=500,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text.strip(), "anthropic"
        except Exception as exc:
            logger.warning("Anthropic draft reply failed: %s", exc)

    return build_local_draft_reply(insight_title, insight_summary, tone=tone), "local_nlp"
