# Báo cáo cá nhân — Day 6

## Dữ liệu và pipeline
- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:** Sách *Pro Git (2nd Edition)* của Scott Chacon & Ben Straub (Apress, giấy phép CC BY-NC-SA 3.0). Phạm vi corpus gồm 47 trang nội dung liên tục (từ trang 19 đến 65) bao gồm toàn bộ Chương 1 (*Getting Started*) và Chương 2 (*Git Basics*). Quy tắc đếm trang: chỉ tính các trang có $\ge 150$ ký tự sau khi chuẩn hóa Unicode NFC, loại bỏ bìa, mục lục và các trang trống.
- **Chuẩn hóa, lỗi và giới hạn:** Chuẩn hóa Unicode sang dạng NFC, chuẩn hóa khoảng trắng liên tục trên từng dòng nhưng bảo toàn cấu trúc phân đoạn (`\n\n`) và tiêu đề phục vụ chia chunk theo cấu trúc. Log trang lỗi/rỗng được ghi nhận chi tiết tại `results/ingestion_log.json`.
- **Embedding model/provider/version/số chiều, vector store/version, metric, lệnh chạy và chi phí:** Sử dụng model OpenAI `text-embedding-3-small` (1536 chiều) qua OpenAI API, Vector Store là PostgreSQL 16 + pgvector 0.8.7 (chạy qua Docker local trên cổng 55433), metric đo khoảng cách Cosine (`<=>`). Chi phí tính theo giá chính thức OpenAI ($0.02 / 1M tokens). Lệnh chạy: `python -m src.run`.
- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn:** Metadata bắt buộc gồm `document_id`, `source`, `page`. Bổ sung trường lọc `chapter` (nhận 2 giá trị phân biệt: `ch01_getting_started` và `ch02_git_basics`) trích xuất tự nhiên theo cấu trúc chương sách để phân lập phạm vi khái niệm cơ bản với các thao tác dòng lệnh chuyên sâu.

## Cấu hình và benchmark
- **A / B / C (tham số cụ thể, khác biệt duy nhất B–C):**
  - **Chiến lược A:** Chunking cố định (`fixed_size = 500` ký tự, `overlap = 50` ký tự), không dùng metadata filter khi truy xuất.
  - **Chiến lược B:** Chunking theo đoạn văn/cấu trúc (`by_paragraph`, `max_size = 600` ký tự, `overlap = 0`), không dùng metadata filter khi truy xuất (so sánh với A để đo lường thuần túy tác động của phương pháp chunking).
  - **Chiến lược C:** Giữ nguyên 100% chunking theo đoạn như B (`by_paragraph`, `max_size = 600`), nhưng kích hoạt metadata filter theo `chapter` khi câu hỏi có yêu cầu filter (khác biệt duy nhất so với B để đo lường tác động của metadata filter).
- **≥20 câu: phân chia ≥15 dev / ≥5 test, câu metadata filter và cách kiểm chứng evidence:** Tổng cộng 20 câu hỏi được lưu tại `benchmark/questions.json`, chia làm 15 câu `dev` (`q01`–`q15`) và 5 câu `test` (`q16`–`q20`). Bao gồm 8 câu trực tiếp, 6 câu diễn đạt lại và 6 câu điều kiện/ngoại lệ. Có 3 câu kiểm tra metadata filter (`q14`, `q15` thuộc dev; `q20` thuộc test). Toàn bộ 20 câu đều được script `scripts/verify_benchmark.py` kiểm chứng tự động khớp 100% với trích dẫn nguyên văn trong trang nguồn.
- **Tiêu chí chọn chiến lược đã chốt trước khi xem test:**
  1. *Tiêu chí 1 (Bắt buộc):* Ưu tiên chiến lược có `Evidence Hit@3` trên tập `dev` cao nhất.
  2. *Tiêu chí 2:* Điểm `Chunk Coherence` trung bình (thang điểm 2) cao hơn để đảm bảo văn bản trích xuất giữ trọn vẹn ý nghĩa cho Agent.
  3. *Tiêu chí 3:* Điểm `Hit@1` trên tập `dev` cao hơn (trong trường hợp Hit@3 bằng nhau).
  4. *Tiêu chí 4:* Số lượng chunk và chi phí token thấp hơn.

## Kết quả
*(Sẽ được điền tự động sau khi chạy Giai đoạn 4 và Giai đoạn 5)*

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | | | | | |
| A | test | | | | | |
| B | dev | | | | | |
| B | test | | | | | |
| C | dev | | | | | |
| C | test | | | | | |

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | | | | |
| B | | | | |
| C | | | | |

Đường dẫn trace, nhãn thủ công và cách chọn mẫu:
- Trace truy xuất: `results/traces.json`
- Chấm thủ công Coherence (10 vị trí nguồn): `results/manual_coherence.csv`
- Kiểm tra Metadata (5 câu test x top-3): `results/manual_metadata_audit.csv`
- Chấm thủ công Grounding (5 câu test): `results/manual_grounding.csv`

## Phân tích và kết luận
*(Sẽ được phân tích chi tiết sau khi có kết quả thực nghiệm)*
