# TÀI LIỆU API — INSIGHTHUB AI

Tài liệu đặc tả REST API cho **Django REST Backend** (`/api/...`) và **FastAPI AI Microservice**.

---

## 1. Quy ước chung & Xác thực

### 1.1. Base URL
| Service | Local Development | Docker Compose (qua Nginx) | Cloud Production (ví dụ) |
|---|---|---|---|
| **Backend API** | `http://localhost:8000/api` | `/api` (proxy sang `backend:8000`) | `https://<backend-domain>/api` |
| **AI Service** | `http://localhost:8001` | `http://ai_service:8001` | `https://<ai-service-domain>` |

### 1.2. Cơ chế xác thực (Headers)
1. **JWT Bearer Authentication** (Backend `/api/...`):
   ```http
   Authorization: Bearer <access_token>
   ```
   - `ACCESS_TOKEN_LIFETIME`: `60` phút; `REFRESH_TOKEN_LIFETIME`: `7` ngày (hỗ trợ xoay vòng + blacklist khi logout).
2. **Webhook Source Token** (cho kênh tiếp nhận ngoài trên `POST /api/sources/ingest/`):
   ```http
   X-Source-Token: <webhook_token>
   ```
   - Dùng khi hệ thống bên ngoài đẩy dữ liệu vào mà không cần đăng nhập JWT. Token demo trong seed data: `wh_web_bepviet_2026`, `wh_email_bepviet_2026`, `wh_chat_bepviet_2026`, `wh_comm_bepviet_2026`.
3. **Internal Service Key** (Django gọi FastAPI AI Service):
   ```http
   X-API-Key: <AI_SERVICE_API_KEY>
   ```
   - AI Service kiểm tra header này khi biến môi trường `AI_SERVICE_API_KEY` được cấu hình khác giá trị placeholder mặc định `change-this-internal-service-secret`.

### 1.3. Phân trang & Định dạng lỗi chuẩn
- **Pagination mặc định**: `PAGE_SIZE = 20` (`page`, `page_size`). Response có cấu trúc `{ "count", "next", "previous", "results" }`. Một số danh mục nhẹ (`roles`, `sources`, `tags`, `roadmap`, `roadmap/public`) tắt phân trang (`pagination_class = None`).
- **Định dạng lỗi (`custom_exception_handler`)**:
  ```json
  {
    "detail": "Dữ liệu không hợp lệ hoặc thao tác bị từ chối.",
    "errors": {
      "field_name": ["Thông báo lỗi chi tiết."]
    }
  }
  ```

---

## 2. Backend REST API (Django + DRF)

### 2.1. Health Check
| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| `GET` | `/api/health/` | Public (`AllowAny`) | Kiểm tra trạng thái backend & kết nối DB (`SELECT 1`). Trả `200 ok` hoặc `503 degraded`. |

---

### 2.2. Authentication, Profile & User Management (`apps.accounts`)

| Method | Endpoint | Quyền | Request Body / Params | Response chính |
|---|---|---|---|---|
| `POST` | `/api/auth/register/` | `AllowAny` | `{ "username", "email", "full_name", "password" }` (mật khẩu >= 8 ký tự) | `201` `{ "access", "refresh", "user" }` (mặc định vai trò `CUSTOMER`) |
| `POST` | `/api/auth/login/` | `AllowAny` | `{ "identifier", "password" }` (`identifier` là email hoặc username) | `200` `{ "access", "refresh", "user" }` |
| `POST` | `/api/auth/logout/` | `IsAuthenticated` | `{ "refresh" }` | `200` `{ "detail": "Đăng xuất thành công." }` (blacklist refresh token) |
| `POST` | `/api/auth/token/refresh/` | `AllowAny` | `{ "refresh" }` | `200` `{ "access", "refresh" }` |
| `GET` | `/api/auth/me/` | `IsAuthenticated` | — | `200` Thông tin user kèm `permissions` |
| `PATCH` | `/api/auth/me/` | `IsAuthenticated` | `{ "full_name", "job_title", "department", "avatar_url", "email_notifications_enabled" }` | `200` Profile đã cập nhật |
| `POST` | `/api/auth/change-password/` | `IsAuthenticated` | `{ "old_password", "new_password" }` | `200` `{ "detail": "Đổi mật khẩu thành công." }` |
| `POST` | `/api/auth/forgot-password/` | `AllowAny` | `{ "email" }` | `200` Tạo `PasswordResetToken` hết hạn sau 30 phút (trả thêm `dev_reset_token` khi `DJANGO_DEBUG=True`) |
| `POST` | `/api/auth/reset-password/` | `AllowAny` | `{ "token", "new_password" }` | `200` Đặt lại mật khẩu thành công |
| `GET` | `/api/roles/` | `IsAuthenticated` | — | Danh sách 5 role hệ thống |
| `GET/POST` | `/api/users/` | Đọc: `IsInternalTeam`; Ghi: `IsAdmin` | Filter `role`, `is_active`, `search` | Danh sách / tạo user (`role_code`, `password`, ...) |
| `GET/PATCH/DELETE` | `/api/users/{id}/` | `UserManagementPermission` | `{ "role_code", "full_name", "is_active", ... }` | Cập nhật thông tin / phân quyền |
| `POST` | `/api/users/{id}/toggle_active/` | `IsAdmin` | — | Đảo trạng thái `is_active` |

#### Ví dụ `POST /api/auth/login/`
```json
// Request
{
  "identifier": "pm@insighthub.vn",
  "password": "InsightDemo!2026"
}

// Response 200 OK
{
  "access": "eyJhbGciOiJIUzI1NiIs...",
  "refresh": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "id": 2,
    "username": "pm_minh",
    "email": "pm@insighthub.vn",
    "full_name": "Trần Quang Minh",
    "display_name": "Trần Quang Minh",
    "role_code": "PRODUCT_MANAGER",
    "role_name": "Product Manager",
    "permissions": ["feedback:*", "insight:*", "kanban:*", "roadmap:*", "ai:run"]
  }
}
```

---

### 2.3. Dashboard, Products, Sources & Tags (`apps.feedbacks`)

| Method | Endpoint | Quyền | Mô tả / Query Params |
|---|---|---|---|
| `GET` | `/api/dashboard/` | `IsAuthenticated` (lọc theo RBAC: Customer chỉ thấy số liệu phản hồi của mình; Developer chỉ thấy mục được gán) | Query: `product`, `days` (7..90, mặc định `30`). Trả `kpis`, `feedbacks_by_date`, `feedbacks_by_source`, `by_priority`, `top_5_issues`, `urgent_insights`. |
| `GET` | `/api/products/` | `AllowAny` (xem danh sách) | Danh sách sản phẩm kèm `feedback_count`. |
| `POST/PATCH/DELETE` | `/api/products/` | `IsPMOrAdmin` | Quản lý sản phẩm (`name`, `slug`, `description`, `category`, `owner`, `is_active`). |
| `GET` | `/api/sources/` | `IsAuthenticated` | Danh sách kênh tiếp nhận (`WEB_FORM`, `EMAIL`, `LIVE_CHAT`, `COMMUNITY`). Trường `webhook_token` bị ẩn với vai trò ngoài `ADMIN`/`PRODUCT_MANAGER`. |
| `GET` | `/api/tags/` | `IsAuthenticated` | Danh sách nhãn (`bug`, `payment`, `delivery`, ...). |
| `POST/PATCH/DELETE` | `/api/tags/` | `IsPMOrAdmin` | Quản lý nhãn (`name`, `slug`, `color`, `description`). |

---

### 2.4. Feedback Inbox & Multi-source Hub (`apps.feedbacks`)

#### Kiểm soát truy cập theo dòng (Row-level RBAC) trên `/api/feedbacks/`:
- `ADMIN`, `PRODUCT_MANAGER`, `CUSTOMER_SUPPORT`: Xem toàn bộ feedback.
- `DEVELOPER`: Chỉ xem feedback được gán trực tiếp (`assigned_to`) hoặc thuộc Insight được gán cho mình.
- `CUSTOMER`: Chỉ xem feedback của chính mình (`author=user` hoặc `sender_email=user.email`); chỉ được sửa/xóa feedback của mình khi `status == "NEW"`; không xem được `comment` có `is_internal=true`.

| Method | Endpoint | Quyền | Mô tả & Payload |
|---|---|---|---|
| `POST` | `/api/sources/ingest/` | JWT **hoặc** `X-Source-Token` | Tiếp nhận phản hồi đa nguồn. Body: `{ "source_code": "EMAIL" \| "LIVE_CHAT" \| "COMMUNITY" \| "WEB_FORM", "product_id"?, "title", "content", "sender_name"?, "sender_email"?, "impact_level"?, "external_reference_id"?, "source_metadata"?, "tag_ids"? }` |
| `GET` | `/api/feedbacks/` | `IsAuthenticated` (theo RBAC) | Query filters: `search`, `status`, `source` (`source__code`), `impact_level`, `priority_level`, `product`, `assigned_to` (`unassigned` hoặc user ID), `tag` (ID hoặc slug), `date_from`, `date_to` (`YYYY-MM-DD`), `unclustered_only=true`, `duplicate_only=true`. |
| `POST` | `/api/feedbacks/` | `IsAuthenticated` | Tạo feedback mới (`title`, `content`, `product`, `source` hoặc `source_code`, `impact_level`, `tag_ids`). |
| `GET/PATCH/DELETE` | `/api/feedbacks/{id}/` | `IsAuthenticated` (kiểm tra quyền theo role trên view) | Xem chi tiết, cập nhật trạng thái/nội dung hoặc xóa theo quyền. |
| `POST` | `/api/feedbacks/{id}/assign/` | `ADMIN`, `PRODUCT_MANAGER`, `CUSTOMER_SUPPORT` | `{ "assigned_to": <user_id | null> }` (tạo thông báo cho người được phân công). |
| `POST` | `/api/feedbacks/{id}/tags/` | `IsInternalTeam` | `{ "tag_ids": [1, 2] }` |
| `POST` | `/api/feedbacks/{id}/mark_duplicate/` | `ADMIN`, `PRODUCT_MANAGER`, `CUSTOMER_SUPPORT` | `{ "duplicate_of_id": <target_id>, "similarity_score"?: 0.89, "confirm"?: true }` |
| `POST` | `/api/feedbacks/{id}/unmark_duplicate/` | `ADMIN`, `PRODUCT_MANAGER`, `CUSTOMER_SUPPORT` | Gỡ đánh dấu trùng lặp. |
| `POST` | `/api/feedbacks/{id}/vote/` | `IsAuthenticated` | Bật/tắt bình chọn (`{"voted": bool, "votes_count": int}`). |
| `GET/POST` | `/api/feedbacks/{id}/comments/` | `IsAuthenticated` | Customer chỉ thấy và chỉ tạo được comment `is_internal=false`. Team nội bộ gửi được `is_internal=true/false`. |
| `GET` | `/api/feedbacks/{id}/activity/` | `IsInternalTeam` | Lịch sử audit trên feedback. |
| `GET` | `/api/feedbacks/{id}/similar/` | `IsInternalTeam` | Query `top_k` (mặc định 6), `min_similarity` (mặc định 0.35). Gọi AI Service `/similarity/search` tìm feedback tương đồng gần nhất. |

---

### 2.5. AI Insight Engine & Kanban Board (`apps.insights`)

> Toàn bộ endpoints dưới đây yêu cầu `IsInternalTeam` (`ADMIN`, `PRODUCT_MANAGER`, `DEVELOPER`, `CUSTOMER_SUPPORT`). Vai trò `CUSTOMER` bị chặn `403 Forbidden`.
> Developer & Customer Support chỉ xem được insight được gán cho mình hoặc đã xác nhận (`VERIFY_CONFIRMED`).

| Method | Endpoint | Quyền | Mô tả & Payload |
|---|---|---|---|
| `POST` | `/api/ai/analyze/` | `IsPMOrAdmin` | Chạy AI Pipeline gom nhóm feedback. Body: `{ "product_id"?, "similarity_threshold": 0.72, "eps": 0.48, "min_samples": 2, "use_llm": true, "include_clustered": false }`. Trả `200 OK` khi `CELERY_ENABLED=False` hoặc `202 Accepted` khi đẩy vào Celery queue. |
| `GET` | `/api/ai/jobs/` | `IsInternalTeam` | Lịch sử các lần chạy `AIAnalysisJob` kèm `metrics`, `duplicate_candidates`, `unassigned_feedback_ids`. |
| `GET` | `/api/ai/unassigned/` | `IsInternalTeam` | Danh sách tối đa 100 feedback chưa thuộc nhóm insight nào (trừ nhóm bị reject và feedback đã xác nhận trùng). |
| `GET` | `/api/insights/` | `IsInternalTeam` | Filters: `status`, `verification_status`, `priority_level`, `product`, `assigned_to`, `search`, `exclude_rejected=true`. |
| `POST` | `/api/insights/` | `IsPMOrAdmin` | Tạo nhóm insight thủ công (`product`, `title`, `description`, `feedback_ids`, ...). |
| `GET/PATCH/DELETE` | `/api/insights/{id}/` | `IsInternalTeam` / `IsPMOrAdmin` | Chi tiết nhóm insight (gồm `members`, `possible_causes`, `ai_recommendations`, `draft_customer_reply`, `priority_reasoning`, `roadmap_items`). |
| `POST` | `/api/insights/{id}/confirm/` | `IsPMOrAdmin` | Xác nhận nhóm insight đề xuất (`VERIFY_CONFIRMED`) và thông báo cho team. |
| `POST` | `/api/insights/{id}/reject/` | `IsPMOrAdmin` | Từ chối nhóm insight đề xuất (`VERIFY_REJECTED`). |
| `POST` | `/api/insights/{id}/override_priority/` | `IsPMOrAdmin` | PM chỉnh tay điểm ưu tiên: `{ "priority_score": 0..100, "priority_level"?, "pm_priority_notes"? }`. |
| `POST` | `/api/insights/{id}/add_feedbacks/` | `IsPMOrAdmin` | `{ "feedback_ids": [12, 15] }` — thêm feedback vào nhóm & tính lại điểm. |
| `POST` | `/api/insights/{id}/remove_feedback/` | `IsPMOrAdmin` | `{ "feedback_id": 12 }` — gỡ feedback khỏi nhóm. |
| `POST` | `/api/insights/{id}/merge/` | `IsPMOrAdmin` | `{ "source_insight_id": 4 }` — gộp nhóm nguồn vào nhóm hiện tại. |
| `POST` | `/api/insights/{id}/split/` | `IsPMOrAdmin` | `{ "feedback_ids": [21, 22], "new_title": "..." }` — tách thành nhóm insight mới (`201 Created`). |
| `POST` | `/api/insights/{id}/move_kanban/` | `ADMIN`, `PM`, hoặc người được phân công | `{ "status"?: "NEW"\|"ANALYZING"\|"PLANNED"\|"IN_PROGRESS"\|"COMPLETED", "assigned_to"?, "due_date"? }`. Đồng bộ trạng thái feedback thành viên khi chuyển sang `PLANNED`/`IN_PROGRESS`/`COMPLETED` và gửi thông báo. |
| `POST` | `/api/insights/{id}/regenerate_reply/` | `IsInternalTeam` | `{ "tone": "empathetic" \| "update" \| "resolved", "use_llm": true }` — tạo lại nháp phản hồi khách hàng qua AI Service. |
| `POST` | `/api/insights/{id}/vote/` | `IsInternalTeam` | Bình chọn nội bộ cho insight. |
| `GET/POST` | `/api/insights/{id}/comments/` | `IsInternalTeam` | Bình luận nội bộ (`is_internal=true`) trên card Kanban / Insight. |
| `GET` | `/api/insights/{id}/activity/` | `IsInternalTeam` | Nhật ký thay đổi trên Insight. |

---

### 2.6. Product Roadmap (`apps.roadmap`)

| Method | Endpoint | Quyền | Mô tả & Payload |
|---|---|---|---|
| `GET` | `/api/roadmap/public/` | `AllowAny` (kể cả chưa đăng nhập & Customer) | Chỉ trả item có `visibility="PUBLIC"` và `status` thuộc `["PLANNED", "IN_PROGRESS", "COMPLETED"]`. Tự động loại bỏ `internal_notes`, `owner_detail` và thông tin nội bộ (`PublicRoadmapItemSerializer`). Filter: `product`, `status`. |
| `GET` | `/api/roadmap/` | `IsInternalTeam` | Private & Public roadmap đầy đủ. Filter: `visibility`, `status`, `product`, `quarter`, `search`. |
| `POST/PATCH/DELETE` | `/api/roadmap/{id}/` | `IsPMOrAdmin` | Tạo/cập nhật roadmap item: `{ "product", "title", "description", "public_description", "internal_notes", "status", "visibility", "quarter", "target_start_date", "target_end_date", "progress_percent": 0..100, "owner", "insight_group_ids": [] }`. |
| `GET/POST` | `/api/roadmap/{id}/comments/` | `IsInternalTeam` | Thảo luận nội bộ trên roadmap item. |

---

### 2.7. Notifications & Audit Logs (`apps.notifications`)

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| `GET` | `/api/notifications/` | `IsAuthenticated` (chỉ trả về `recipient = request.user`) | Filter: `unread_only=true`, `event_type`. Customer chỉ nhận thông báo về feedback của mình hoặc roadmap public. |
| `GET` | `/api/notifications/unread_count/` | `IsAuthenticated` | `{ "unread_count": 3 }` |
| `POST` | `/api/notifications/{id}/mark_read/` | `IsAuthenticated` | Đánh dấu 1 thông báo đã đọc. |
| `POST` | `/api/notifications/mark_all_read/` | `IsAuthenticated` | Đánh dấu toàn bộ thông báo của user hiện tại đã đọc. |
| `GET` | `/api/activity-logs/` | `IsInternalTeam` | Nhật ký hệ thống; filter `entity_type`, `entity_id`. |

---

## 3. FastAPI AI Microservice API

| Method | Endpoint | Header | Request chính | Response chính |
|---|---|---|---|---|
| `GET` | `/health` | — | — | `{ "status": "ok", "service": "insighthub-ai-service", "provider", "openai_configured", "anthropic_configured" }` |
| `POST` | `/embed` | `X-API-Key` | `{ "items": [FeedbackInput...], "use_llm": true }` | `{ "embedding_model", "embeddings": [{ "feedback_id", "normalized_text", "embedding", "embedding_model" }] }` |
| `POST` | `/similarity/search` | `X-API-Key` | `{ "target": FeedbackInput, "candidates": [...], "top_k": 5, "min_similarity": 0.35, "use_llm": true }` | `{ "embedding_model", "matches": [{ "feedback_id", "code", "title", "similarity_score", "is_exact_normalized_match" }] }` |
| `POST` | `/summarize` | `X-API-Key` | `{ "feedbacks": [FeedbackInput...], "total_inbox_count"?, "use_llm": true, "custom_title"? }` | `{ "title", "summary", "possible_causes", "user_impact", "ai_recommendations", "draft_customer_reply", "analysis_mode", "ai_confidence", "volume_score", "impact_score", "severity_score", "priority_score", "priority_level", "priority_reasoning", "affected_customers_count" }` |
| `POST` | `/draft-reply` | `X-API-Key` | `{ "insight_title", "insight_summary", "sample_feedbacks": [...], "tone": "empathetic"\|"update"\|"resolved", "use_llm": true }` | `{ "draft_reply", "analysis_mode", "tone" }` |
| `POST` | `/analyze` | `X-API-Key` | `{ "feedbacks": [FeedbackInput...], "similarity_threshold": 0.72, "eps": 0.48, "min_samples": 2, "use_llm": true, "total_inbox_count"? }` | `{ "embedding_model", "analysis_mode", "embeddings", "duplicate_candidates", "clusters", "unassigned_feedback_ids", "stats" }` |

### Mô hình `FeedbackInput`
```json
{
  "id": 43,
  "code": "FB-0043",
  "title": "Lỗi thanh toán MoMo báo timeout",
  "content": "Đơn hàng 185k bị trừ tiền trên MoMo nhưng app vẫn báo lỗi timeout.",
  "impact_level": "CRITICAL",
  "votes_count": 3,
  "sender_email": "customer1@gmail.com",
  "sender_name": "Nguyễn Minh An",
  "source_code": "LIVE_CHAT",
  "submitted_at": "2026-11-12T10:30:00Z"
}
```
