import os
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.accounts.serializers import ensure_default_roles
from apps.feedbacks.models import Feedback, FeedbackSource, FeedbackTag, Product, Tag
from apps.insights.models import InsightFeedback, InsightGroup
from apps.notifications.models import ActivityLog, Comment, Notification, Vote
from apps.roadmap.models import RoadmapItem, RoadmapItemInsight


class Command(BaseCommand):
    help = "Seed realistic Vietnamese demo data for InsightHub AI (Food Delivery domain)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Clear existing demo domain data before reseeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options.get("reset"):
            self.stdout.write("Resetting existing domain records...")
            Notification.objects.all().delete()
            ActivityLog.objects.all().delete()
            Comment.objects.all().delete()
            Vote.objects.all().delete()
            RoadmapItemInsight.objects.all().delete()
            RoadmapItem.objects.all().delete()
            InsightFeedback.objects.all().delete()
            InsightGroup.objects.all().delete()
            FeedbackTag.objects.all().delete()
            Feedback.objects.all().delete()

        if Feedback.objects.exists() and not options.get("reset"):
            self.stdout.write(
                self.style.WARNING("Database already has feedbacks. Pass --reset to recreate demo dataset.")
            )
            return

        demo_password = os.getenv("DEMO_USER_PASSWORD", "InsightDemo!2026")
        roles = ensure_default_roles()

        users_spec = [
            ("admin", "admin@insighthub.vn", "Trần Quốc Bảo", Role.ADMIN, "System Administrator", "Platform Ops"),
            ("pm_minh", "pm@insighthub.vn", "Nguyễn Nhật Minh", Role.PRODUCT_MANAGER, "Lead Product Manager", "Product"),
            ("dev_tuan", "dev@insighthub.vn", "Lê Anh Tuấn", Role.DEVELOPER, "Senior Mobile & Backend Dev", "Engineering"),
            ("cs_linh", "cs@insighthub.vn", "Phạm Thùy Linh", Role.CUSTOMER_SUPPORT, "Customer Support Lead", "CSKH"),
            ("customer_an", "an.nguyen@gmail.com", "Nguyễn Hoài An", Role.CUSTOMER, "Khách hàng thân thiết", "External"),
            ("customer_huong", "huong.tran@gmail.com", "Trần Mai Hương", Role.CUSTOMER, "Khách hàng", "External"),
            ("customer_duc", "duc.le@gmail.com", "Lê Minh Đức", Role.CUSTOMER, "Khách hàng", "External"),
            ("customer_vy", "vy.pham@gmail.com", "Phạm Thảo Vy", Role.CUSTOMER, "Khách hàng", "External"),
        ]

        users: dict[str, User] = {}
        for username, email, full_name, role_code, title, dept in users_spec:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "full_name": full_name,
                    "role": roles[role_code],
                    "job_title": title,
                    "department": dept,
                    "is_staff": role_code == Role.ADMIN,
                    "is_superuser": role_code == Role.ADMIN,
                },
            )
            if created:
                user.set_password(demo_password)
                user.save()
            users[username] = user

        product, _ = Product.objects.get_or_create(
            slug="bep-viet-go",
            defaults={
                "name": "Bếp Việt Go — Đặt Đồ Ăn Trực Tuyến",
                "description": "Nền tảng đặt đồ ăn nhanh và giao món đa quán trên iOS, Android và Web.",
                "category": "Food Delivery / Mobile & Web App",
                "owner": users["pm_minh"],
            },
        )

        sources_spec = [
            (FeedbackSource.WEB_FORM, "Website Form", "WEB", "Biểu mẫu góp ý trực tiếp trên website & cổng khách hàng", "wh_web_bepviet_2026"),
            (FeedbackSource.EMAIL, "Email Support", "EMAIL", "Phản hồi khách hàng gửi về hòm thư hotro@bepvietgo.vn", "wh_email_bepviet_2026"),
            (FeedbackSource.LIVE_CHAT, "Live Chat", "CHAT", "Hội thoại hỗ trợ trực tuyến trong ứng dụng", "wh_chat_bepviet_2026"),
            (FeedbackSource.COMMUNITY, "Community Forum", "COMMUNITY", "Diễn đàn cộng đồng người dùng & hội nhóm đánh giá", "wh_comm_bepviet_2026"),
        ]
        sources: dict[str, FeedbackSource] = {}
        for code, name, ch, desc, token in sources_spec:
            src, _ = FeedbackSource.objects.get_or_create(
                code=code,
                defaults={"name": name, "channel_type": ch, "description": desc, "webhook_token": token},
            )
            sources[code] = src

        tags_spec = [
            ("Thanh toán", "thanh-toan", "#EF4444"),
            ("Giao hàng", "giao-hang", "#F97316"),
            ("Thông báo", "thong-bao", "#8B5CF6"),
            ("Khuyến mãi", "khuyen-mai", "#10B981"),
            ("Định vị & Tìm kiếm", "dinh-vi-tim-kiem", "#3B82F6"),
            ("Hiệu năng & Crash", "hieu-nang-crash", "#EC4899"),
            ("Đăng nhập & OTP", "dang-nhap-otp", "#06B6D4"),
            ("Tính năng mới", "tinh-nang-moi", "#64748B"),
        ]
        tags: dict[str, Tag] = {}
        for name, slug, color in tags_spec:
            tag, _ = Tag.objects.get_or_create(slug=slug, defaults={"name": name, "color": color})
            tags[slug] = tag

        customers = [
            users["customer_an"],
            users["customer_huong"],
            users["customer_duc"],
            users["customer_vy"],
        ]

        # 54 natural Vietnamese feedbacks across 4 sources & multiple problem clusters
        # Groups: C1 (Payment: 10), C2 (Delivery ETA: 9), C3 (Notifications: 8),
        # C4 (Voucher: 8), C5 (GPS/Search: 7), Unclustered for live AI demo (12) = 54 total
        feedback_specs = [
            # --- Cluster 1: Lỗi thanh toán (10) ---
            ("Không thể thanh toán đơn hàng bằng thẻ", "Mình bấm thanh toán đơn hàng bằng thẻ Visa nhưng hệ thống báo lỗi không xử lý được giao dịch.", "WEB_FORM", "CRITICAL", "thanh-toan", 1),
            ("Thanh toán bị lỗi khi dùng ví MoMo", "Khi chọn thanh toán qua MoMo ứng dụng quay vòng rồi báo thanh toán thất bại dù số dư vẫn đủ.", "EMAIL", "CRITICAL", "thanh-toan", 1),
            ("Ứng dụng không xử lý giao dịch thẻ ATM nội địa", "Nhập OTP ngân hàng xong nhưng app không xác nhận thanh toán đơn hàng.", "LIVE_CHAT", "CRITICAL", "thanh-toan", 1),
            ("Thanh toán bị trừ tiền nhưng đơn chưa xác nhận", "Ví ZaloPay báo đã trừ 185.000đ nhưng app Bếp Việt Go vẫn hiển thị chưa thanh toán.", "EMAIL", "CRITICAL", "thanh-toan", 1),
            ("Giao dịch thanh toán bị treo ở bước xác nhận", "Bấm nút thanh toán đơn trưa bị treo màn hình hơn 2 phút rồi thoát ra.", "WEB_FORM", "HIGH", "thanh-toan", 1),
            ("Không thể thanh toán đơn hàng giờ cao điểm", "Buổi trưa 12h thử thanh toán thẻ 3 lần đều báo lỗi cổng thanh toán.", "COMMUNITY", "HIGH", "thanh-toan", 1),
            ("Lỗi thanh toán khi đổi phương thức sang thẻ", "Ban đầu chọn tiền mặt rồi đổi sang thanh toán bằng thẻ thì nút đặt món bị lỗi.", "LIVE_CHAT", "HIGH", "thanh-toan", 1),
            ("App báo lỗi thanh toán đơn hàng liên tục", "Không thể thanh toán đơn hàng, đã thử cả thẻ lẫn ví đều thất bại.", "WEB_FORM", "CRITICAL", "thanh-toan", 1),
            ("Không thanh toán được bằng Apple Pay / thẻ", "Hệ thống báo giao dịch không thành công ở bước thanh toán cuối cùng.", "COMMUNITY", "HIGH", "thanh-toan", 1),
            ("Thanh toán thất bại nhưng vẫn giữ giỏ hàng lỗi", "Sau khi thanh toán bị lỗi, quay lại giỏ hàng bị mất lựa chọn topping.", "EMAIL", "MEDIUM", "thanh-toan", 1),

            # --- Cluster 2: Giao hàng chậm & ETA sai lệch (9) ---
            ("Đơn hàng giao quá lâu so với dự kiến", "App hiển thị giao trong 20 phút nhưng thực tế gần 55 phút mới nhận được đồ ăn.", "WEB_FORM", "HIGH", "giao-hang", 2),
            ("Tài xế đến muộn hơn 35 phút", "Tài xế nhận đơn xong đứng yên rất lâu rồi mới di chuyển, giao đồ bị nguội.", "EMAIL", "HIGH", "giao-hang", 2),
            ("Thời gian giao hàng không chính xác vào giờ trưa", "Ước tính 15 phút nhưng shipper giao chậm thành 45 phút mà không có cảnh báo.", "COMMUNITY", "HIGH", "giao-hang", 2),
            ("Shipper giao hàng chậm do ghép quá nhiều đơn", "Thấy tài xế đi giao vòng qua 2 quận khác trước khi tới chỗ mình.", "LIVE_CHAT", "HIGH", "giao-hang", 2),
            ("Dự kiến giao hàng nhảy thời gian liên tục", "Lúc đầu báo 18 phút, 10 phút sau lại tăng lên 38 phút không rõ lý do.", "WEB_FORM", "MEDIUM", "giao-hang", 2),
            ("Giao đồ ăn bị trễ hẹn hơn nửa tiếng", "Đặt cơm trưa văn phòng lúc 11h15 nhưng 12h20 tài xế mới tới nơi.", "EMAIL", "HIGH", "giao-hang", 2),
            ("Thời gian giao hàng thực tế chênh lệch quá lớn", "Mong cải thiện ETA dự đoán giao hàng vào ngày mưa để khách chủ động.", "COMMUNITY", "MEDIUM", "giao-hang", 2),
            ("Tài xế giao trễ khiến món bị nguội lạnh", "Đơn bún chả giao mất hơn 50 phút, tài xế đến muộn xin lỗi vì app điều đơn xa.", "LIVE_CHAT", "HIGH", "giao-hang", 2),
            ("App không báo khi đơn có nguy cơ giao chậm", "Nếu quán làm lâu hoặc shipper kẹt đường nên báo sớm cho người mua.", "WEB_FORM", "MEDIUM", "giao-hang", 2),

            # --- Cluster 3: Lỗi thông báo đơn hàng (8) ---
            ("Không nhận được thông báo khi tài xế đến", "Shipper đứng dưới sảnh gọi điện mới biết chứ ứng dụng không gửi thông báo gì.", "WEB_FORM", "HIGH", "thong-bao", 3),
            ("Ứng dụng không báo trạng thái quán đã xác nhận", "Phải mở app kiểm tra thủ công liên tục vì không có push notification.", "LIVE_CHAT", "HIGH", "thong-bao", 3),
            ("Tắt mở lại thông báo vẫn không nhận được tin báo đơn", "Đã bật full quyền thông báo trên iOS 18 nhưng app không hề rung hay báo.", "EMAIL", "HIGH", "thong-bao", 3),
            ("Thông báo tài xế đang đến bị gửi chậm 10 phút", "Nhận được đồ ăn xong rồi app mới nhảy thông báo tài xế sắp tới.", "COMMUNITY", "MEDIUM", "thong-bao", 3),
            ("Không có chuông báo khi shipper nhắn tin trong app", "Tài xế nhắn hỏi cổng vào nhưng không có thông báo đẩy nên mình không đọc kịp.", "LIVE_CHAT", "HIGH", "thong-bao", 3),
            ("Mất toàn bộ thông báo khuyến mãi và đơn hàng", "Từ bản cập nhật tuần trước, thanh thông báo không hiển thị cập nhật đơn nữa.", "WEB_FORM", "MEDIUM", "thong-bao", 3),
            ("App không thông báo khi đơn bị quán hủy món", "Quán hết món mà ứng dụng không báo đẩy, mãi sau mở vào mới thấy.", "EMAIL", "HIGH", "thong-bao", 3),
            ("Cần thông báo rõ hơn lúc tài xế tới gần 200m", "Rất nhiều lần bỏ lỡ shipper vì app không gửi thông báo nhắc nhận hàng.", "COMMUNITY", "MEDIUM", "thong-bao", 3),

            # --- Cluster 4: Lỗi áp dụng mã giảm giá / Voucher (8) ---
            ("Không áp dụng được mã giảm giá dù đủ điều kiện", "Đơn 160k trên mức tối thiểu 120k nhưng bấm chọn voucher báo không hợp lệ.", "WEB_FORM", "HIGH", "khuyen-mai", 4),
            ("Voucher freeship tự động bị gỡ khi đổi món", "Thêm một ly trà đá vào giỏ hàng là mã giảm giá đang chọn bị biến mất.", "LIVE_CHAT", "MEDIUM", "khuyen-mai", 4),
            ("Không rõ lý do tại sao mã khuyến mãi bị từ chối", "App chỉ báo chung chung 'Không thể áp dụng mã' mà không ghi thiếu điều kiện gì.", "COMMUNITY", "MEDIUM", "khuyen-mai", 4),
            ("Mã giảm giá thành viên mới báo đã sử dụng dù chưa đặt", "Mình mới tạo tài khoản lần đầu nhưng nhập voucher tân thủ lại báo hết lượt.", "EMAIL", "HIGH", "khuyen-mai", 4),
            ("Số tiền giảm thực tế không khớp với mô tả voucher", "Ghi giảm 30k nhưng khi ra màn hình thanh toán chỉ trừ 15k.", "WEB_FORM", "HIGH", "khuyen-mai", 4),
            ("Mục chọn khuyến mãi tải rất chậm và hay trùng mã", "Danh sách voucher hiển thị nhiều mã hết hạn xen kẽ mã còn dùng được.", "COMMUNITY", "LOW", "khuyen-mai", 4),
            ("Nên tự động áp dụng voucher giảm nhiều nhất", "Phải bấm thử từng mã khuyến mãi rất mất thời gian trước khi đặt món.", "WEB_FORM", "MEDIUM", "khuyen-mai", 4),
            ("Lỗi mất mã giảm giá sau khi thanh toán thử lại", "Thanh toán lỗi một lần rồi đặt lại thì mã khuyến mãi báo đã bị khóa.", "EMAIL", "HIGH", "khuyen-mai", 4),

            # --- Cluster 5: Định vị GPS & Tìm kiếm món ăn (7) ---
            ("Định vị GPS tự nhảy sai sang tòa nhà bên cạnh", "Mình ở chung cư block B nhưng bản đồ cứ tự ghim sang block A cách 300m.", "WEB_FORM", "HIGH", "dinh-vi-tim-kiem", 5),
            ("Tìm kiếm món ăn không dấu trả về kết quả sai", "Gõ 'bun bo hue' không dấu thì không ra các quán bún bò Huế gần nhà.", "COMMUNITY", "MEDIUM", "dinh-vi-tim-kiem", 5),
            ("Không lưu được ghi chú cổng giao cho địa chỉ quen", "Mỗi lần đặt lại phải gõ lại hướng dẫn đường đi vào hẻm cho shipper.", "LIVE_CHAT", "MEDIUM", "dinh-vi-tim-kiem", 5),
            ("Bản đồ chọn vị trí bị lag khi kéo ghim", "Kéo điểm ghim địa chỉ giao hàng trên Android bị giật và sai lệch tọa độ.", "EMAIL", "MEDIUM", "dinh-vi-tim-kiem", 5),
            ("Bộ lọc tìm quán đang mở cửa hoạt động chưa chuẩn", "Lọc quán mở cửa nhưng vẫn hiện nhiều quán đã đóng bếp khi bấm vào.", "WEB_FORM", "MEDIUM", "dinh-vi-tim-kiem", 5),
            ("Sai địa chỉ giao hàng khi dùng vị trí hiện tại", "Bấm định vị tự động ngoài đường nhưng app lấy địa chỉ cũ hôm qua.", "LIVE_CHAT", "HIGH", "dinh-vi-tim-kiem", 5),
            ("Cần gợi ý tìm kiếm theo món ăn kèm đánh giá", "Tìm 'cơm tấm' hiện quán cách 8km lên đầu thay vì quán gần 1km.", "COMMUNITY", "LOW", "dinh-vi-tim-kiem", 5),

            # --- Unclustered Feedbacks (12) để giảng viên/PM chạy AI Engine trực tiếp ---
            ("Ứng dụng bị giật lag khi lướt thực đơn nhiều ảnh", "Vào các quán có trên 50 món là app cuộn rất giật và nóng máy.", "WEB_FORM", "HIGH", "hieu-nang-crash", None),
            ("App tự văng đột ngột khi mở trang chi tiết quán", "Trên Android 14 cứ bấm xem hình ảnh món ăn là ứng dụng bị crash thoát ra.", "EMAIL", "CRITICAL", "hieu-nang-crash", None),
            ("Tải thực đơn bị treo đứng máy khi mạng 4G yếu", "Mở giỏ hàng và danh sách món đứng màn hình trắng khá lâu.", "LIVE_CHAT", "HIGH", "hieu-nang-crash", None),
            ("Giật lag và thoát app khi phóng to ảnh món ăn", "Bấm xem ảnh review món ăn của người dùng là app bị đứng rồi văng ra.", "COMMUNITY", "HIGH", "hieu-nang-crash", None),

            ("Mã OTP đăng nhập gửi về SMS rất chậm", "Chờ hơn 3 phút mới nhận được mã OTP nên hết thời gian xác thực đăng nhập.", "LIVE_CHAT", "HIGH", "dang-nhap-otp", None),
            ("Không đăng nhập được do lỗi xác thực OTP liên tục", "Nhập đúng mã OTP vừa nhận nhưng hệ thống báo mã đăng nhập không hợp lệ.", "EMAIL", "CRITICAL", "dang-nhap-otp", None),
            ("App tự đăng xuất tài khoản sau mỗi ngày", "Ngày nào mở app cũng bắt đăng nhập lại và chờ mã OTP rất bất tiện.", "WEB_FORM", "MEDIUM", "dang-nhap-otp", None),
            ("Lỗi đăng nhập bằng tài khoản Google trên iOS", "Bấm tiếp tục với Google bị quay vòng rồi quay lại màn hình đăng nhập.", "COMMUNITY", "HIGH", "dang-nhap-otp", None),

            ("Đề xuất bổ sung chế độ giao diện tối Dark Mode", "Đặt đồ ăn buổi tối nhìn nền trắng khá chói mắt, mong có Dark Mode.", "COMMUNITY", "LOW", "tinh-nang-moi", None),
            ("Cần tính năng xuất hóa đơn VAT cho đơn đặt nhóm", "Công ty mình hay đặt ăn trưa chung, cần xuất hóa đơn điện tử tự động.", "EMAIL", "MEDIUM", "tinh-nang-moi", None),
            ("Cho phép đặt hẹn giờ giao cố định vào sáng hôm sau", "Muốn đặt sẵn từ tối hôm trước để 11h30 trưa hôm sau quán tự giao.", "WEB_FORM", "MEDIUM", "tinh-nang-moi", None),
            ("Bổ sung mục đánh giá riêng độ đóng gói của quán", "Muốn tách điểm đánh giá tài xế và điểm đóng gói đồ ăn của nhà hàng.", "COMMUNITY", "LOW", "tinh-nang-moi", None),
        ]

        now = timezone.now()
        created_feedbacks: list[Feedback] = []
        cluster_members_map: dict[int, list[Feedback]] = {1: [], 2: [], 3: [], 4: [], 5: []}

        for idx, (title, content, src_code, impact, tag_slug, cluster_num) in enumerate(feedback_specs):
            cust = customers[idx % len(customers)]
            days_ago = max(0, 24 - (idx * 24 // len(feedback_specs)))
            submitted_time = now - timedelta(days=days_ago, hours=(idx * 3) % 18)

            status_val = Feedback.STATUS_NEW
            assigned_user = None
            if cluster_num == 1:
                status_val = Feedback.STATUS_IN_PROGRESS
                assigned_user = users["dev_tuan"]
            elif cluster_num == 2:
                status_val = Feedback.STATUS_PLANNED
                assigned_user = users["dev_tuan"]
            elif cluster_num == 3:
                status_val = Feedback.STATUS_ANALYZING
                assigned_user = users["cs_linh"]
            elif cluster_num == 4:
                status_val = Feedback.STATUS_COMPLETED
                assigned_user = users["dev_tuan"]
            elif cluster_num == 5:
                status_val = Feedback.STATUS_ANALYZING
                assigned_user = users["cs_linh"]

            fb = Feedback.objects.create(
                title=title,
                content=content,
                normalized_content=f"{title}. {content}",
                author=cust,
                sender_name=cust.display_name(),
                sender_email=cust.email,
                product=product,
                source=sources[src_code],
                status=status_val,
                impact_level=impact,
                assigned_to=assigned_user,
                submitted_at=submitted_time,
                source_metadata={
                    "channel": src_code,
                    "device": "iOS 18" if idx % 2 == 0 else "Android 14",
                    "app_version": "3.4.2",
                },
            )
            FeedbackTag.objects.create(feedback=fb, tag=tags[tag_slug], added_by=users["pm_minh"])
            created_feedbacks.append(fb)
            if cluster_num:
                cluster_members_map[cluster_num].append(fb)

            # Seed sample upvotes
            for voter in customers[: (idx % 4) + 1]:
                Vote.objects.get_or_create(user=voter, feedback=fb)

        # Mark one realistic confirmed duplicate in cluster 1 for demo clarity
        dup_fb = created_feedbacks[7]
        orig_fb = created_feedbacks[0]
        dup_fb.duplicate_of = orig_fb
        dup_fb.similarity_score = 0.89
        dup_fb.is_duplicate_confirmed = True
        dup_fb.status = Feedback.STATUS_DUPLICATE
        dup_fb.save(update_fields=["duplicate_of", "similarity_score", "is_duplicate_confirmed", "status"])

        # Seed 5 Insight Groups matching clusters 1..5
        insights_spec = [
            (
                1,
                "Lỗi & trục trặc quy trình thanh toán đơn hàng",
                "Nhóm gồm 10 phản hồi mức độ nghiêm trọng cao về việc không thể hoàn tất thanh toán qua thẻ Visa/ATM, ví MoMo/ZaloPay hoặc bị trừ tiền nhưng đơn chưa xác nhận.",
                [
                    "Giả thuyết cần kiểm tra: timeout kết nối tới cổng thanh toán giờ cao điểm trưa (11h30–13h00).",
                    "Giả thuyết cần kiểm tra: webhook đối soát trạng thái giao dịch giữa ví điện tử và hệ thống đơn hàng chưa đồng bộ kịp.",
                ],
                "Khách hàng không thể hoàn tất đặt món hoặc hoang mang khi bị trừ tiền nhưng đơn chưa ghi nhận, ảnh hưởng trực tiếp doanh thu.",
                [
                    "Kiểm tra log giao dịch thất bại theo cổng thanh toán và bổ sung cơ chế idempotency + retry an toàn.",
                    "Hiển thị màn hình trạng thái chờ đối soát rõ ràng kèm nút kiểm tra lại giao dịch / hoàn tiền tự động.",
                ],
                "Chào bạn,\n\nChúng tôi thành thật xin lỗi vì sự cố khi thanh toán đơn hàng của bạn. Đội ngũ kỹ thuật Bếp Việt Go đang ưu tiên kiểm tra kết nối cổng thanh toán và cơ chế đối soát giao dịch.\n\nNếu tài khoản của bạn đã bị trừ tiền nhưng chưa lên đơn, hệ thống sẽ tự động hoàn soát trong vòng 24h hoặc bạn có thể nhắn mã đơn cho CSKH để được hỗ trợ ngay.\n\nTrân trọng,\nĐội ngũ Bếp Việt Go",
                91.4, 88.0, 92.5, 90.8, InsightGroup.PRIORITY_CRITICAL,
                "Điểm tổng hợp 90.8/100 (CRITICAL) = 0.40×V(91.4) + 0.35×I(88.0) + 0.25×S(92.5). Có 10 phản hồi từ 4 nhóm khách hàng, nhiều báo cáo mức Critical chặn trực tiếp luồng thanh toán.",
                InsightGroup.STATUS_IN_PROGRESS, InsightGroup.VERIFY_CONFIRMED, users["dev_tuan"], 4,
            ),
            (
                2,
                "Giao hàng chậm và sai lệch thời gian dự kiến (ETA)",
                "9 phản hồi phản ánh thời gian giao hàng thực tế chậm hơn 25–40 phút so với ETA hiển thị trên app, đặc biệt vào khung giờ cao điểm trưa và ngày mưa.",
                [
                    "Giả thuyết cần kiểm tra: mô hình ước lượng ETA hiện tại chưa cập nhật trọng số kẹt xe và thời gian quán chuẩn bị món giờ cao điểm.",
                    "Giả thuyết cần kiểm tra: thuật toán ghép nhiều đơn cho cùng tài xế làm kéo dài lộ trình giao.",
                ],
                "Giảm trải nghiệm chất lượng món ăn (đồ ăn bị nguội) và tăng tỷ lệ hủy đơn hoặc phàn nàn CSKH.",
                [
                    "Hiệu chỉnh mô hình dự báo ETA theo dữ liệu lịch sử từng khung giờ và khu vực.",
                    "Gửi thông báo chủ động khi đơn dự kiến trễ quá 10 phút kèm lý do minh bạch.",
                ],
                "Chào bạn,\n\nCảm ơn bạn đã góp ý về thời gian giao hàng trên Bếp Việt Go. Chúng tôi đang nâng cấp hệ thống ước tính ETA theo mật độ giao thông và tốc độ chuẩn bị của từng quán để hiển thị thời gian chính xác hơn.\n\nTrân trọng,\nĐội ngũ Sản phẩm Bếp Việt Go",
                84.0, 74.0, 72.0, 77.5, InsightGroup.PRIORITY_HIGH,
                "Điểm tổng hợp 77.5/100 (HIGH) = 0.40×V(84.0) + 0.35×I(74.0) + 0.25×S(72.0). Tác động trực tiếp đến trải nghiệm nhận món đúng giờ.",
                InsightGroup.STATUS_PLANNED, InsightGroup.VERIFY_CONFIRMED, users["dev_tuan"], 10,
            ),
            (
                3,
                "Thiếu hoặc chậm thông báo trạng thái đơn và khi tài xế đến",
                "8 phản hồi ghi nhận người dùng không nhận được push notification khi quán xác nhận, tài xế nhắn tin hoặc khi shipper đã tới điểm giao.",
                [
                    "Giả thuyết cần kiểm tra: token FCM/APNs trên iOS 18 và một số thiết bị Android chưa được làm mới đúng chu kỳ.",
                    "Giả thuyết cần kiểm tra: sự kiện cập nhật vị trí tài xế vào bán kính 200m chưa kích hoạt cảnh báo đẩy.",
                ],
                "Khách hàng bỏ lỡ cuộc gọi/tin nhắn nhận đồ ăn và phải mở lại ứng dụng kiểm tra thủ công nhiều lần.",
                [
                    "Kiểm tra tỷ lệ delivery push notification theo hệ điều hành và thêm kênh thông báo in-app realtime.",
                    "Bổ sung thông báo nhắc nhận hàng khi tài xế cách điểm giao 200m.",
                ],
                "Chào bạn,\n\nCảm ơn bạn đã phản ánh vấn đề thông báo đơn hàng. Đội ngũ kỹ thuật đã tiếp nhận và đang kiểm tra lại dịch vụ gửi thông báo trên cả iOS và Android để đảm bảo bạn luôn nhận được cập nhật kịp thời.\n\nTrân trọng,\nĐội ngũ Bếp Việt Go",
                76.5, 71.0, 68.0, 72.5, InsightGroup.PRIORITY_HIGH,
                "Điểm tổng hợp 72.5/100 (HIGH) = 0.40×V(76.5) + 0.35×I(71.0) + 0.25×S(68.0). Ảnh hưởng xuyên suốt hành trình theo dõi đơn.",
                InsightGroup.STATUS_ANALYZING, InsightGroup.VERIFY_CONFIRMED, users["cs_linh"], 7,
            ),
            (
                4,
                "Khó khăn khi áp dụng mã giảm giá & voucher khuyến mãi",
                "8 phản hồi cho biết voucher bị từ chối không rõ lý do, tự động mất khi sửa giỏ hàng hoặc số tiền giảm chưa rõ ràng.",
                [
                    "Giả thuyết cần kiểm tra: UI hiện chỉ trả mã lỗi chung chung mà không nêu điều kiện còn thiếu (giá trị đơn tối thiểu, phương thức thanh toán).",
                    "Giả thuyết cần kiểm tra: sự kiện cập nhật giỏ hàng làm reset trạng thái voucher đã chọn.",
                ],
                "Người dùng tốn thời gian thử từng mã hoặc hụt hẫng ở bước thanh toán, làm tăng tỷ lệ bỏ giỏ hàng.",
                [
                    "Hiển thị rõ lý do không đủ điều kiện ngay dưới từng voucher và hỗ trợ tự động chọn mã ưu đãi tốt nhất.",
                    "Giữ nguyên trạng thái voucher hợp lệ khi chỉnh sửa món trong giỏ hàng.",
                ],
                "Chào bạn,\n\nTin vui! Đội ngũ Bếp Việt Go đã hoàn tất nâng cấp giao diện chọn Voucher: hệ thống sẽ tự động gợi ý mã giảm giá tốt nhất và hiển thị rõ điều kiện áp dụng cho từng mã.\n\nCảm ơn bạn đã góp ý giúp sản phẩm tốt hơn!",
                72.0, 62.0, 56.0, 64.5, InsightGroup.PRIORITY_HIGH,
                "Điểm tổng hợp 64.5/100 (HIGH) = 0.40×V(72.0) + 0.35×I(62.0) + 0.25×S(56.0).",
                InsightGroup.STATUS_COMPLETED, InsightGroup.VERIFY_CONFIRMED, users["dev_tuan"], -2,
            ),
            (
                5,
                "Sai lệch định vị GPS chung cư và tìm kiếm món không dấu",
                "7 phản hồi về ghim GPS lệch sang tòa nhà kế bên, tìm kiếm món không dấu chưa chuẩn và thiếu lưu ghi chú cổng giao hàng.",
                [
                    "Giả thuyết cần kiểm tra: dữ liệu POI tòa nhà/chung cư ở một số khu đô thị mới chưa có điểm đón chi tiết.",
                    "Giả thuyết cần kiểm tra: bộ tìm kiếm full-text chưa chuẩn hóa đồng nhất chuỗi tiếng Việt không dấu.",
                ],
                "Tài xế và khách hàng mất thời gian gọi điện xác nhận lại cổng giao và khó tìm quán gần.",
                [
                    "Cho phép lưu ghi chú cổng/tòa nhà gắn với từng địa chỉ đã lưu và cho phép kéo ghim mượt hơn.",
                    "Bổ sung index tìm kiếm tiếng Việt không dấu kết hợp khoảng cách ưu tiên quán gần.",
                ],
                "Chào bạn,\n\nCảm ơn bạn đã chia sẻ về trải nghiệm định vị và tìm kiếm món ăn. Chúng tôi đang ghi nhận các khu vực chung cư thường lệch ghim để tối ưu bản đồ chọn điểm giao hàng.\n\nTrân trọng,\nĐội ngũ Bếp Việt Go",
                64.0, 55.0, 46.0, 56.4, InsightGroup.PRIORITY_MEDIUM,
                "Điểm tổng hợp 56.4/100 (MEDIUM) = 0.40×V(64.0) + 0.35×I(55.0) + 0.25×S(46.0).",
                InsightGroup.STATUS_NEW, InsightGroup.VERIFY_PENDING, users["cs_linh"], 14,
            ),
        ]

        created_insights: dict[int, InsightGroup] = {}
        for (
            c_idx, title, desc, causes, impact_txt, recs, reply,
            v_sc, i_sc, s_sc, p_sc, p_lvl, p_reason, k_status, v_status, assignee, due_delta
        ) in insights_spec:
            ins = InsightGroup.objects.create(
                product=product,
                title=title,
                description=desc,
                possible_causes=causes,
                user_impact=impact_txt,
                ai_recommendations=recs,
                draft_customer_reply=reply,
                analysis_mode="local_nlp",
                ai_confidence=0.89,
                volume_score=v_sc,
                impact_score=i_sc,
                severity_score=s_sc,
                priority_score=p_sc,
                priority_level=p_lvl,
                priority_reasoning=p_reason,
                status=k_status,
                verification_status=v_status,
                assigned_to=assignee,
                due_date=(now + timedelta(days=due_delta)).date(),
                created_by=users["pm_minh"],
            )
            for m_idx, fb in enumerate(cluster_members_map[c_idx]):
                InsightFeedback.objects.create(
                    insight_group=ins,
                    feedback=fb,
                    similarity_to_centroid=round(0.92 - m_idx * 0.03, 4),
                    added_by_ai=True,
                    added_by=users["pm_minh"],
                )
                fb.priority_score = ins.priority_score
                fb.save(update_fields=["priority_score"])
            ins.sync_counts()
            created_insights[c_idx] = ins

        # Seed comments on insights & feedbacks
        Comment.objects.create(
            author=users["pm_minh"],
            insight_group=created_insights[1],
            content="Đã kiểm tra sơ bộ với team Payment Gateway: tập trung tái hiện luồng timeout khung 12h trưa.",
            is_internal=True,
        )
        Comment.objects.create(
            author=users["dev_tuan"],
            insight_group=created_insights[1],
            content="Đang triển khai idempotency key và retry callback MoMo/ZaloPay trong sprint hiện tại.",
            is_internal=True,
        )
        Comment.objects.create(
            author=users["cs_linh"],
            feedback=created_feedbacks[0],
            content="Chào bạn An, CSKH đã ghi nhận mã giao dịch và chuyển đội kỹ thuật ưu tiên xử lý trong hôm nay.",
            is_internal=False,
        )
        Comment.objects.create(
            author=users["dev_tuan"],
            feedback=created_feedbacks[0],
            content="[Internal] Trace ID #pay-9921 cho thấy gateway trả 504 sau 15s.",
            is_internal=True,
        )

        # Seed 5 Roadmap Items (4 PUBLIC + 1 PRIVATE)
        roadmap_specs = [
            (
                "Ổn định cổng thanh toán & đối soát tự động giao dịch treo",
                "Nâng cấp luồng thanh toán thẻ/ví với idempotency key, webhook retry và màn hình đối soát trạng thái tức thì.",
                "Nâng cấp độ ổn định khi thanh toán bằng thẻ và ví điện tử, bổ sung thông báo trạng thái rõ ràng khi mạng chậm.",
                "[Nội bộ] Refactor PaymentOrchestratorService + bổ sung Redis lock chống double-charge.",
                RoadmapItem.STATUS_IN_PROGRESS,
                RoadmapItem.VISIBILITY_PUBLIC,
                "Q4 2026",
                -7, 10, 65, users["dev_tuan"], [1],
            ),
            (
                "Dự báo thời gian giao hàng thông minh (Smart ETA v2)",
                "Áp dụng dữ liệu khung giờ cao điểm, thời tiết và tốc độ chuẩn bị món tại quán để dự đoán ETA chính xác hơn.",
                "Cải thiện độ chính xác của thời gian giao hàng dự kiến và cảnh báo sớm nếu đơn có nguy cơ giao chậm.",
                "[Nội bộ] Kết nối pipeline telemetry tài xế theo zone quận 1, 3, 7, Bình Thạnh.",
                RoadmapItem.STATUS_PLANNED,
                RoadmapItem.VISIBILITY_PUBLIC,
                "Q4 2026",
                5, 35, 15, users["dev_tuan"], [2],
            ),
            (
                "Nâng cấp hệ thống Push Notification & nhắc nhận hàng 200m",
                "Sửa lỗi mất token thông báo trên iOS 18 và gửi thông báo đẩy kèm âm báo khi tài xế sắp tới điểm giao.",
                "Đảm bảo thông báo trạng thái đơn và nhắc nhận hàng khi tài xế đến nơi luôn hiển thị đúng lúc.",
                "[Nội bộ] Migrate lên FCM HTTP v1 + silent push heartbeat check.",
                RoadmapItem.STATUS_PLANNED,
                RoadmapItem.VISIBILITY_PUBLIC,
                "Q1 2027",
                14, 45, 10, users["cs_linh"], [3],
            ),
            (
                "Tự động gợi ý Voucher tối ưu & hiển thị rõ điều kiện",
                "Hiển thị điều kiện chi tiết của từng mã giảm giá, giữ voucher khi sửa giỏ hàng và tự đề xuất mã giảm sâu nhất.",
                "Tự động gợi ý mã khuyến mãi tốt nhất và giải thích rõ ràng điều kiện áp dụng tại giỏ hàng.",
                "[Nội bộ] Đã deploy bản 3.4.3 lên 100% người dùng, tỷ lệ áp dụng voucher thành công tăng 18%.",
                RoadmapItem.STATUS_COMPLETED,
                RoadmapItem.VISIBILITY_PUBLIC,
                "Q4 2026",
                -25, -2, 100, users["dev_tuan"], [4],
            ),
            (
                "[Internal] Tái cấu trúc Search Index & Bản đồ POI nội bộ",
                "Chuyển cụm tìm kiếm sang cấu trúc chuẩn hóa không dấu tiếng Việt và tích hợp bản đồ POI chung cư nội bộ.",
                "",
                "[Bảo mật nội bộ] Đánh giá chi phí API bản đồ vs OpenStreetMap + Elasticsearch Vietnamese analyzer.",
                RoadmapItem.STATUS_PLANNED,
                RoadmapItem.VISIBILITY_PRIVATE,
                "Q1 2027",
                20, 60, 5, users["pm_minh"], [5],
            ),
        ]

        created_roadmaps: list[RoadmapItem] = []
        for (
            title, desc, pub_desc, int_notes, st, vis, quarter,
            start_off, end_off, progress, owner, insight_keys
        ) in roadmap_specs:
            rm = RoadmapItem.objects.create(
                product=product,
                title=title,
                description=desc,
                public_description=pub_desc,
                internal_notes=int_notes,
                status=st,
                visibility=vis,
                quarter=quarter,
                target_start_date=(now + timedelta(days=start_off)).date(),
                target_end_date=(now + timedelta(days=end_off)).date(),
                progress_percent=progress,
                owner=owner,
                created_by=users["pm_minh"],
            )
            for k in insight_keys:
                RoadmapItemInsight.objects.create(roadmap_item=rm, insight_group=created_insights[k])
            created_roadmaps.append(rm)

        # Seed notifications for PM, Dev, CS, and Customers
        Notification.objects.create(
            recipient=users["pm_minh"],
            actor=users["customer_an"],
            event_type=Notification.EVENT_FEEDBACK_RECEIVED,
            title="[CRITICAL] Phản hồi mới về lỗi thanh toán",
            message="Khách hàng Nguyễn Hoài An vừa báo lỗi không thể thanh toán đơn hàng bằng thẻ Visa.",
            feedback=created_feedbacks[0],
            link_url=f"/inbox/{created_feedbacks[0].id}",
        )
        Notification.objects.create(
            recipient=users["dev_tuan"],
            actor=users["pm_minh"],
            event_type=Notification.EVENT_INSIGHT_CONFIRMED,
            title=f"Insight {created_insights[1].code} cần xử lý khẩn cấp",
            message="Nhóm vấn đề thanh toán đạt điểm ưu tiên 90.8/100 (CRITICAL) và đã được chuyển sang In Progress.",
            insight_group=created_insights[1],
            link_url=f"/insights/{created_insights[1].id}",
        )
        Notification.objects.create(
            recipient=users["customer_an"],
            actor=users["pm_minh"],
            event_type=Notification.EVENT_ROADMAP_UPDATED,
            title="Phản hồi của bạn đang được xử lý trên Lộ trình Sản phẩm",
            message="Hạng mục 'Ổn định cổng thanh toán & đối soát tự động' đang ở trạng thái In Progress (65%).",
            feedback=created_feedbacks[0],
            roadmap_item=created_roadmaps[0],
            link_url="/public-roadmap",
        )
        Notification.objects.create(
            recipient=users["customer_vy"],
            actor=users["dev_tuan"],
            event_type=Notification.EVENT_ISSUE_COMPLETED,
            title="Cải tiến về Mã giảm giá đã hoàn thành!",
            message="Tính năng tự động gợi ý Voucher tối ưu liên quan đến góp ý của bạn đã chính thức ra mắt.",
            roadmap_item=created_roadmaps[3],
            link_url="/public-roadmap",
        )

        ActivityLog.objects.create(
            actor=users["pm_minh"],
            entity_type=ActivityLog.ENTITY_INSIGHT,
            entity_id=created_insights[1].id,
            action="CONFIRMED",
            description=f"Xác nhận nhóm insight {created_insights[1].code} và phân công cho Lê Anh Tuấn",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded successfully: {User.objects.count()} users, "
                f"{Feedback.objects.count()} feedbacks, "
                f"{InsightGroup.objects.count()} insight groups, "
                f"{RoadmapItem.objects.count()} roadmap items."
            )
        )
