# Giải Thích Chi Tiết Ý Nghĩa Các Bảng Và Các Cột Trong Database — InsightHub AI

Tài liệu này giải thích chi tiết mục đích và ý nghĩa từng cột của **13 bảng nghiệp vụ chính** (đã tối giản từ 17 bảng gốc) trong cơ sở dữ liệu **InsightHub AI**.

*(4 bảng phụ đã loại bỏ: `activity_logs`, `ai_analysis_jobs`, `password_reset_tokens`, `comments`.)*

---

## PHẦN A: NHÓM QUẢN LÝ NGƯỜI DÙNG & PHÂN QUYỀN (2 BẢNG)

### 1. Bảng `roles` — Vai trò phân quyền (5 cột)
Lưu danh sách 5 vai trò trong hệ thống (`ADMIN`, `PRODUCT_MANAGER`, `DEVELOPER`, `CUSTOMER_SUPPORT`, `CUSTOMER`) và danh sách chức năng được phép truy cập.

| Tên cột | Kiểu dữ liệu | Ý nghĩa |
|---|---|---|
| `id` | `BIGINT` (PK) | Mã định danh tự tăng của vai trò (Khóa chính). |
| `code` | `VARCHAR(32)` | Mã vai trò duy nhất (`ADMIN`, `PRODUCT_MANAGER`, `DEVELOPER`, `CUSTOMER_SUPPORT`, `CUSTOMER`). |
| `name` | `VARCHAR(100)` | Tên hiển thị của vai trò (VD: *Product Manager*, *Customer Support*). |
| `description` | `TEXT` | Mô tả trách nhiệm của vai trò. |
| `permissions` | `JSONB` | Danh sách mã chức năng được cấp cho vai trò (`dashboard`, `inbox`, `sources`, `insights`, `ai_run`, `kanban`, `roadmap`, `users`). |

### 2. Bảng `users` — Người dùng & Nhân sự (12 cột)
Lưu thông tin tài khoản của cả nhân sự nội bộ (Admin, PM, Dev, CSKH) và khách hàng (Customer).

| Tên cột | Kiểu dữ liệu | Ý nghĩa |
|---|---|---|
| `id` | `BIGINT` (PK) | Mã định danh tự tăng của người dùng. |
| `username` | `VARCHAR(150)` | Tên đăng nhập duy nhất. |
| `email` | `VARCHAR(254)` | Email duy nhất dùng đăng nhập và nhận thông báo. |
| `password` | `VARCHAR(128)` | Mật khẩu đã mã hóa `PBKDF2-SHA256`. |
| `full_name` | `VARCHAR(150)` | Họ và tên đầy đủ của người dùng. |
| `role_id` | `BIGINT` (FK) | Khóa ngoại trỏ tới `roles(id)`. |
| `job_title` | `VARCHAR(120)` | Chức danh công việc (VD: *Lead Product Manager*, *Senior Dev*). |
| `is_active` | `BOOLEAN` | Trạng thái kích hoạt tài khoản. |
| `is_staff` | `BOOLEAN` | Cờ cho phép truy cập `/admin/` của Django. |
| `is_superuser` | `BOOLEAN` | Cờ tài khoản quản trị tối cao. |
| `last_login` | `TIMESTAMPTZ` | Thời điểm đăng nhập gần nhất. |
| `date_joined` | `TIMESTAMPTZ` | Thời điểm tài khoản được tạo. |

---

## PHẦN B: NHÓM SẢN PHẨM & THU THẬP PHẢN HỒI ĐA KÊNH (5 BẢNG)

### 3. Bảng `products` — Sản phẩm (6 cột)
| Tên cột | Kiểu dữ liệu | Ý nghĩa |
|---|---|---|
| `id` | `BIGINT` (PK) | Khóa chính tự tăng. |
| `name` | `VARCHAR(150)` | Tên sản phẩm (VD: *Bếp Việt Go*). |
| `slug` | `VARCHAR(160)` | Chuỗi đường dẫn thân thiện duy nhất. |
| `description` | `TEXT` | Mô tả sản phẩm. |
| `is_active` | `BOOLEAN` | Trạng thái sản phẩm đang hoạt động. |
| `created_at` | `TIMESTAMPTZ` | Thời điểm tạo sản phẩm. |

### 4. Bảng `feedback_sources` — Nguồn tiếp nhận phản hồi (4 cột)
| Tên cột | Kiểu dữ liệu | Ý nghĩa |
|---|---|---|
| `id` | `BIGINT` (PK) | Khóa chính tự tăng. |
| `code` | `VARCHAR(32)` | Mã kênh (`WEB_FORM`, `EMAIL`, `LIVE_CHAT`, `COMMUNITY`). |
| `name` | `VARCHAR(100)` | Tên hiển thị của kênh. |
| `is_active` | `BOOLEAN` | Trạng thái bật/tắt kênh. |

### 5. Bảng `tags` — Nhãn phân loại chủ đề (4 cột)
| Tên cột | Kiểu dữ liệu | Ý nghĩa |
|---|---|---|
| `id` | `BIGINT` (PK) | Khóa chính tự tăng. |
| `name` | `VARCHAR(60)` | Tên nhãn duy nhất (VD: *Thanh toán*, *Giao hàng*). |
| `slug` | `VARCHAR(70)` | Mã không dấu duy nhất. |
| `color` | `VARCHAR(20)` | Mã màu HEX hiển thị trên giao diện. |

### 6. Bảng `feedbacks` — Phản hồi khách hàng (19 cột)
| Tên cột | Kiểu dữ liệu | Ý nghĩa |
|---|---|---|
| `id` | `BIGINT` (PK) | Khóa chính tự tăng. |
| `code` | `VARCHAR(24)` | Mã hiển thị duy nhất (`FB-0001`, `FB-0002`...). |
| `title` | `VARCHAR(255)` | Tiêu đề ngắn gọn của phản hồi. |
| `content` | `TEXT` | Nội dung chi tiết phản hồi. |
| `ai_summary` | `TEXT` | Bản tóm tắt ngắn gọn do AI sinh ra cho từng feedback. |
| `author_id` | `BIGINT` (FK) | Tài khoản người gửi (trỏ tới `users.id`). |
| `sender_name` | `VARCHAR(150)` | Tên người gửi (dùng cho phản hồi đa nguồn giả lập). |
| `sender_email` | `VARCHAR(254)` | Email người gửi. |
| `product_id` | `BIGINT` (FK) | Sản phẩm liên quan (`products.id`). |
| `source_id` | `BIGINT` (FK) | Kênh tiếp nhận (`feedback_sources.id`). |
| `status` | `VARCHAR(24)` | Trạng thái Kanban: `NEW`, `REVIEWING`, `PLANNED`, `DONE`, `DUPLICATE`. |
| `impact_level` | `VARCHAR(16)` | Mức ảnh hưởng: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. |
| `priority_score` | `DOUBLE` | Điểm ưu tiên (0–100). |
| `assigned_to_id` | `BIGINT` (FK) | Nhân sự được giao xử lý (`users.id`). |
| `duplicate_of_id` | `BIGINT` (FK) | Tự tham chiếu về feedback gốc nếu bị trùng lặp. |
| `similarity_score` | `DOUBLE` | Độ tương đồng Cosine (0.0–1.0) so với feedback gốc. |
| `is_duplicate_confirmed` | `BOOLEAN` | Đánh dấu đã xác nhận trùng lặp. |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | Thời điểm tạo và cập nhật gần nhất. |

### 7. Bảng `feedback_tags` — Bảng trung gian Feedback & Tag (3 cột)
| Tên cột | Kiểu dữ liệu | Ý nghĩa |
|---|---|---|
| `id` | `BIGINT` (PK) | Khóa chính tự tăng. |
| `feedback_id` | `BIGINT` (FK) | Khóa ngoại trỏ tới `feedbacks(id)`. |
| `tag_id` | `BIGINT` (FK) | Khóa ngoại trỏ tới `tags(id)`. |

---

## PHẦN C: NHÓM PHÂN TÍCH AI & GOM CỤM INSIGHT (2 BẢNG)

### 8. Bảng `insight_groups` — Nhóm vấn đề do AI tổng hợp (18 cột)
| Tên cột | Kiểu dữ liệu | Ý nghĩa |
|---|---|---|
| `id` | `BIGINT` (PK) | Khóa chính tự tăng. |
| `code` | `VARCHAR(24)` | Mã Insight duy nhất (`INS-001`...). |
| `product_id` | `BIGINT` (FK) | Khóa ngoại trỏ tới `products(id)`. |
| `title` | `VARCHAR(255)` | Tên nhóm vấn đề do AI tóm tắt. |
| `description` | `TEXT` | Tóm tắt tổng hợp các feedback thành viên. |
| `possible_causes` | `JSONB` | Danh sách nguyên nhân khả dĩ do AI phân tích. |
| `ai_recommendations` | `JSONB` | Đề xuất hướng khắc phục cho đội sản phẩm. |
| `draft_customer_reply` | `TEXT` | Nháp câu trả lời khách hàng do AI tạo. |
| `volume_score` / `impact_score` / `severity_score` | `DOUBLE` | 3 thành phần điểm thành phần $V, I, S$ (0–100). |
| `priority_score` | `DOUBLE` | Điểm ưu tiên $= 0.4 \times V + 0.35 \times I + 0.25 \times S$. |
| `priority_level` | `VARCHAR(16)` | Xếp hạng: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`. |
| `status` | `VARCHAR(24)` | Cột Kanban (`NEW`, `REVIEWING`, `PLANNED`, `DONE`). |
| `verification_status` | `VARCHAR(24)` | Trạng thái duyệt của PM: `PENDING_REVIEW`, `CONFIRMED`, `REJECTED`. |
| `feedback_count` | `INTEGER` | Tổng số feedback thuộc nhóm Insight. |
| `assigned_to_id` | `BIGINT` (FK) | Nhân sự phụ trách (`users.id`). |
| `created_at` | `TIMESTAMPTZ` | Thời điểm tạo nhóm Insight. |

### 9. Bảng `insight_feedbacks` — Bảng trung gian Insight & Feedback (4 cột)
| Tên cột | Kiểu dữ liệu | Ý nghĩa |
|---|---|---|
| `id` | `BIGINT` (PK) | Khóa chính tự tăng. |
| `insight_group_id` | `BIGINT` (FK) | Khóa ngoại trỏ tới `insight_groups(id)`. |
| `feedback_id` | `BIGINT` (FK) | Khóa ngoại trỏ tới `feedbacks(id)`. |
| `similarity_to_centroid` | `DOUBLE` | Độ tương đồng ngữ nghĩa so với tâm cụm (0.0–1.0). |

---

## PHẦN D: NHÓM LỘ TRÌNH SẢN PHẨM — PRODUCT ROADMAP (2 BẢNG)

### 10. Bảng `roadmap_items` — Hạng mục lộ trình sản phẩm (12 cột)
| Tên cột | Kiểu dữ liệu | Ý nghĩa |
|---|---|---|
| `id` | `BIGINT` (PK) | Khóa chính tự tăng. |
| `code` | `VARCHAR(24)` | Mã hạng mục (`RM-001`...). |
| `product_id` | `BIGINT` (FK) | Khóa ngoại trỏ tới `products(id)`. |
| `title` | `VARCHAR(255)` | Tên hạng mục trên Roadmap. |
| `description` | `TEXT` | Mô tả chi tiết dành cho nội bộ. |
| `public_description` | `TEXT` | Mô tả thân thiện hiển thị trên trang **Public Roadmap**. |
| `status` | `VARCHAR(24)` | `PLANNED`, `IN_PROGRESS`, `COMPLETED`. |
| `visibility` | `VARCHAR(16)` | `PUBLIC` (khách xem được) hoặc `PRIVATE` (nội bộ). |
| `quarter` | `VARCHAR(32)` | Quý dự kiến (VD: `Q4 2026`). |
| `progress_percent` | `SMALLINT` | Tiến độ hoàn thành (0–100%). |
| `owner_id` | `BIGINT` (FK) | Người phụ trách (`users.id`). |
| `updated_at` | `TIMESTAMPTZ` | Thời điểm cập nhật gần nhất. |

### 11. Bảng `roadmap_item_insights` — Liên kết Roadmap & Insight (3 cột)
| Tên cột | Kiểu dữ liệu | Ý nghĩa |
|---|---|---|
| `id` | `BIGINT` (PK) | Khóa chính tự tăng. |
| `roadmap_item_id` | `BIGINT` (FK) | Khóa ngoại trỏ tới `roadmap_items(id)`. |
| `insight_group_id` | `BIGINT` (FK) | Khóa ngoại trỏ tới `insight_groups(id)`. |

---

## PHẦN E: NHÓM TƯƠNG TÁC & THÔNG BÁO (2 BẢNG)

### 12. Bảng `votes` — Lượt bình chọn (4 cột)
| Tên cột | Kiểu dữ liệu | Ý nghĩa |
|---|---|---|
| `id` | `BIGINT` (PK) | Khóa chính tự tăng. |
| `user_id` | `BIGINT` (FK) | Người bình chọn (`users.id`). |
| `feedback_id` | `BIGINT` (FK) | Phản hồi được bình chọn (`NULL` nếu vote cho Insight). |
| `insight_group_id` | `BIGINT` (FK) | Nhóm Insight được bình chọn (`NULL` nếu vote cho Feedback). |

### 13. Bảng `notifications` — Thông báo cho người dùng (8 cột)
| Tên cột | Kiểu dữ liệu | Ý nghĩa |
|---|---|---|
| `id` | `BIGINT` (PK) | Khóa chính tự tăng. |
| `recipient_id` | `BIGINT` (FK) | Người nhận thông báo (`users.id`). |
| `event_type` | `VARCHAR(32)` | Loại sự kiện (`FEEDBACK_RECEIVED`, `STATUS_CHANGED`, `INSIGHT_CONFIRMED`, `ROADMAP_UPDATED`, `ISSUE_COMPLETED`...). |
| `title` | `VARCHAR(255)` | Tiêu đề thông báo. |
| `message` | `TEXT` | Nội dung chi tiết thông báo. |
| `feedback_id` | `BIGINT` (FK) | Phản hồi liên quan (nếu có). |
| `is_read` | `BOOLEAN` | Trạng thái đã đọc (`True`/`False`). |
| `created_at` | `TIMESTAMPTZ` | Thời điểm tạo thông báo. |
