# Tài Liệu Thuật Toán AI — InsightHub AI Engine

## 1. Mục Tiêu Thuật Toán

AI Insight Engine xử lý tập feedback thô đa nguồn và chuyển hóa thành **Insight có cấu trúc, định lượng mức ưu tiên và gắn bằng chứng**, phục vụ Product Discovery.

Toàn bộ pipeline gồm **6 bước tính toán thực tế** chạy trong FastAPI microservice (`ai_service/`):

```
Raw Feedbacks
   │
   ▼ [Step 1] Text Preprocessing & Normalization
Normalized Text + Exact/Near-Exact Pre-check
   │
   ▼ [Step 2] Vector Embedding (OpenAI / Local Multilingual TF-IDF + SVD)
L2-Normalized Dense Vectors (R^d)
   │
   ▼ [Step 3] Pairwise Cosine Similarity Search
Duplicate Candidates (>= threshold, human-verified)
   │
   ▼ [Step 4] DBSCAN Clustering (metric='cosine')
Clusters (Insight Candidates) + Noise (Unassigned Feedbacks)
   │
   ▼ [Step 5] Grounded Summarization & Draft Customer Reply (LLM or NLP Engine)
Title, Summary, Possible Causes, User Impact, Recommendations, Draft Reply
   │
   ▼ [Step 6] Priority Scoring (0.4V + 0.35I + 0.25S)
Score [0..100] + Priority Level + Quantitative Reasoning
```

---

## 2. Chi Tiết Từng Bước

### Bước 1: Tiền xử lý văn bản (Preprocessing)
1. Chuẩn hóa Unicode về dạng `NFC` (đảm bảo dấu tiếng Việt đồng nhất).
2. Loại bỏ HTML tags, URL dư thừa, email signature nhiễu và khoảng trắng thừa (`re.sub(r"\s+", " ", text).strip()`).
3. Ghép `title + ". " + content` thành `combined_text` để vector giữ cả chủ đề lẫn chi tiết.
4. Kiểm tra rỗng và phát hiện trùng lặp ký tự chuẩn hóa tuyệt đối (`exact_normalized_hash`).

### Bước 2: Tạo Embedding Vector (Text Embedding)
Hệ thống hỗ trợ 2 chế độ embedding thực tế:
1. **OpenAI Embedding Mode** (khi có `OPENAI_API_KEY` và `use_llm=True`):
   - Gọi model `text-embedding-3-small` để biểu diễn ngữ nghĩa đa ngôn ngữ (bao gồm tiếng Việt).
2. **Local Multilingual ML Mode** (mặc định khi chạy local / không gắn API key trả phí, hoặc fallback khi API key lỗi):
   - Kết hợp 2 không gian đặc trưng `FeatureUnion`:
     - **Word n-grams (1, 2)** kết hợp chuẩn hóa văn bản tiếng Việt + tách âm tiết (`sublinear_tf=True`).
     - **Character wb n-grams (3, 5)** giúp bắt chính xác biến thể chính tả, gõ thiếu dấu hoặc từ ghép tiếng Việt (ví dụ *"thanh toán"* vs *"thanh toan"*, *"tài xế"* vs *"shipper"* nếu kèm từ ngữ cảnh).
   - Chiếu qua **TruncatedSVD** (`n_components` tự co giãn theo kích thước tập mẫu, tối đa 128 chiều) và **L2-normalize** vector để mọi vector đều nằm trên mặt cầu đơn vị, đảm bảo tích vô hướng bằng đúng Cosine Similarity.
   - *Lý do thiết kế*: Không phụ thuộc GPU hay tải model PyTorch >1GB giúp chạy ổn định dưới ngưỡng RAM 512MB của Render Free Tier, đồng thời sẵn sàng nâng cấp lên OpenAI embeddings chỉ bằng một biến môi trường.

### Bước 3: Similarity Search & Phát Hiện Trùng Lặp
Công thức Cosine Similarity giữa hai vector $A$ và $B$:

$$\text{similarity}(A, B) = \frac{A \cdot B}{\|A\| \cdot \|B\|}$$

- Tính ma trận tương đồng toàn cục $S \in [-1, 1]^{N \times N}$ bằng phép nhân ma trận `vectors @ vectors.T` (đã L2-normalized).
- Với mỗi cặp $(i, j)$ có $\text{similarity}(i, j) \ge \tau$ (ngưỡng cấu hình mặc định $\tau = 0.72$, điều chỉnh được từ 0.50 đến 0.95):
  - Đưa vào danh sách **Duplicate Candidates** (ứng viên trùng lặp).
  - **Nguyên tắc kiểm soát**: Hệ thống chỉ gắn cờ gợi ý và điểm tương đồng (`similarity_score`), **không tự động xóa hay khóa vĩnh viễn**; Product Manager / Admin kiểm tra trực tiếp trên giao diện để bấm **Xác nhận trùng lặp** hoặc **Bỏ qua**.
- Ngoài ra cung cấp endpoint `/similarity/search` để tìm top-k feedback tương tự theo thời gian thực khi xem chi tiết 1 feedback.

### Bước 4: Gom Nhóm Feedback (DBSCAN Clustering)
Sử dụng thuật toán **DBSCAN** (`sklearn.cluster.DBSCAN`) trên ma trận khoảng cách cosine:

$$d(A, B) = \max(0, 1 - \text{similarity}(A, B))$$

- Tham số cấu hình:
  - `eps` (mặc định `0.48`, tương ứng độ tương đồng $\ge 0.52$).
  - `min_samples` (mặc định `2` — tối thiểu 2 feedback tương tự để hình thành một nhóm Insight).
- **Ưu điểm của DBSCAN**:
  - Không cần biết trước số lượng cụm $k$ như K-Means.
  - Tự động gắn nhãn `-1` cho các phản hồi đơn lẻ/ngoại lai (**Unassigned / Noise Feedbacks**) để PM xử lý riêng hoặc gom thủ công, thay vì ép vào sai nhóm.
- Với từng cụm tìm được:
  - Tính **centroid vector** = trung bình L2-normalized của các vector thành viên.
  - Tính `similarity_to_centroid` cho từng feedback thành viên để xếp hạng mức độ đại diện.

### Bước 5: Tóm Tắt Vấn Đề, Đề Xuất Hướng Xử Lý & Tạo Nháp Phản Hồi
- **Chế độ LLM (OpenAI / Claude API)**:
  - Gửi danh sách feedback đại diện + thống kê nguồn + tác động kèm ràng buộc chống bịa đặt (*"Chỉ nêu nguyên nhân có khả năng xảy ra dưới dạng giả thuyết dựa trên nội dung feedback, tuyệt đối không khẳng định nguyên nhân kỹ thuật nội bộ khi dữ liệu không chứng minh"*).
  - Xuất JSON chuẩn: `title`, `summary`, `possible_causes[]`, `user_impact`, `ai_recommendations[]`, `draft_customer_reply`.
- **Chế độ Local NLP Summarizer** (khi không có LLM API key):
  - Dùng thuật toán trích xuất cụm từ đặc trưng TF-IDF trong cụm (so sánh TF-IDF nội cụm vs toàn cục) để đặt tên chủ đề chính xác.
  - Chọn tối đa 3 feedback có `similarity_to_centroid` cao nhất làm câu cốt lõi để tổng hợp `summary`.
  - Đối chiếu từ khóa mức độ nghiêm trọng (lỗi thanh toán, crash, mất dữ liệu, chậm trễ...) để sinh giả thuyết nguyên nhân thận trọng (*"Có dấu hiệu liên quan đến..."*), phân tích tác động và tạo nháp phản hồi khách hàng theo ngữ cảnh thực tế của cụm.

### Bước 6: Tính Điểm Ưu Tiên (Priority Scoring)
Công thức định lượng trên thang `0–100`:

$$\text{Priority} = 0.40 \times V + 0.35 \times I + 0.25 \times S$$

Trong đó mỗi thành phần được chuẩn hóa về `[0, 100]`:
1. **V (Volume — 40%)**:
   - Kết hợp số lượng feedback trong nhóm (`cluster_size`), số lượng khách hàng duy nhất bị ảnh hưởng (`unique_customers`) và lượt vote cộng dồn (`total_votes`), chuẩn hóa logarit/tuyến tính so với quy mô toàn bộ inbox hiện tại để tránh 1-2 feedback lẻ đạt điểm 100 tuyệt đối.
2. **I (Impact — 35%)**:
   - Dựa trên phân bố trường `impact_level` (`CRITICAL=100, HIGH=75, MEDIUM=45, LOW=20`) cộng trọng số từ các từ khóa ảnh hưởng đến trải nghiệm cốt lõi (thanh toán, đặt món, đăng nhập, giao hàng).
3. **S (Severity — 25%)**:
   - Dựa trên mức độ khẩn cấp/nghiêm trọng ngôn ngữ (lỗi chặn luồng hoàn toàn, treo app, trừ tiền nhầm, mất dữ liệu, lỗi bảo mật) và tỷ lệ feedback có mức `CRITICAL`/`HIGH`.

Phân loại mức độ ưu tiên:
- `80 – 100`: **CRITICAL**
- `60 – 79.9`: **HIGH**
- `40 – 59.9`: **MEDIUM**
- `0 – 39.9`: **LOW**

Mỗi Insight đều lưu `priority_reasoning` giải thích chi tiết điểm thành phần `(V, I, S)` và cho phép **Product Manager chỉnh sửa thủ công** (`is_priority_overridden=True`, kèm `pm_priority_notes`).
