# Báo cáo cá nhân — Day 6

## Dữ liệu và pipeline
- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:** Sách giáo trình kỹ thuật chính thức *Pro Git (2nd Edition)* của Scott Chacon & Ben Straub (Apress, phát hành công khai dưới giấy phép Creative Commons Attribution Non Commercial Share Alike 3.0 - CC BY-NC-SA 3.0). Phạm vi corpus gồm 47 trang nội dung liên tục (từ trang vật lý 19 đến 65) bao gồm toàn bộ Chương 1 (*Getting Started*) và Chương 2 (*Git Basics*). Quy tắc đếm trang: chỉ tính các trang có $\ge 150$ ký tự sau khi chuẩn hóa Unicode NFC, loại bỏ bìa, mục lục và trang trống.
- **Chuẩn hóa, lỗi và giới hạn:** Chuẩn hóa Unicode sang dạng NFC (`unicodedata.normalize('NFC')`), chuyển đổi các khoảng trắng đặc biệt (`\xa0`) và gộp khoảng trắng liên tục trên từng dòng thành 1 dấu cách nhưng bảo toàn cấu trúc ngắt đoạn văn (`\n\n`) và tiêu đề. Toàn bộ 47/47 trang trong phạm vi chỉ định đều đạt chuẩn trích xuất văn bản (tổng 88.341 ký tự), không có trang bị lỗi extract text (ghi nhận chi tiết tại [results/ingestion_log.json]).
- **Embedding model/provider/version/số chiều, vector store/version, metric, lệnh chạy và chi phí:** Sử dụng model OpenAI `text-embedding-3-small` (1536 chiều) thông qua thư viện chính thức `openai` (v3.50.0). Vector Store là PostgreSQL 16 + pgvector 0.8.7 (chạy trên Docker container local cổng 55433), khoảng cách đo Cosine (`<=>` trong pgvector, Cosine similarity = $1 - \text{distance}$). Tổng chi phí embedding toàn bộ corpus chỉ là **$0.000907** (~23 VNĐ) cho 45.340 tokens. Lệnh chạy ingestion: `python -m starter.src.run`.
- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn:** Metadata bắt buộc gắn trên từng chunk gồm `document_id` (`progit-v2`), `source` (`data/progit.pdf`), `page` (trang vật lý). Trường lọc bổ sung là `chapter` nhận 2 giá trị phân biệt: `ch01_getting_started` (trang 19–32) và `ch02_git_basics` (trang 33–65). Nguồn giá trị trích xuất trực tiếp từ cấu trúc phân chương của sách nhằm giúp AI Agent lọc đúng phạm vi ngữ cảnh khi người dùng hỏi về thiết lập ban đầu hay thao tác lệnh nâng cao.

## Cấu hình và benchmark
- **A / B / C (tham số cụ thể, khác biệt duy nhất B–C):**
  - **Chiến lược A:** Chia chunk cửa sổ cố định `fixed_size = 500` ký tự, `overlap = 50` ký tự, sinh 215 chunks, truy xuất thuần Cosine không lọc.
  - **Chiến lược B:** Chia chunk theo cấu trúc đoạn văn/heading `by_paragraph` (`max_size = 600` ký tự, `overlap = 0`, gộp đoạn ngắn), sinh 191 chunks, truy xuất thuần Cosine không lọc (so sánh có kiểm soát A–B để đo ảnh hưởng của phương pháp chunking).
  - **Chiến lược C:** Sử dụng cùng tập chunks và vector embedding như Chiến lược B (191 chunks), nhưng kích hoạt metadata filtering theo `chapter` khi câu hỏi có trường `filter` (so sánh có kiểm soát B–C để đo ảnh hưởng thuần túy của metadata filter).
- **≥20 câu: phân chia ≥15 dev / ≥5 test, câu metadata filter và cách kiểm chứng evidence:** Bộ 20 câu hỏi được lưu tại [benchmark/questions.json], tách sẵn cố định 15 câu `dev` (`q01`–`q15`) và 5 câu `test` (`q16`–`q20`). Bao gồm 8 câu hỏi trực tiếp (`truc_tiep`), 6 câu diễn đạt lại (`dien_dat_lai`) và 6 câu điều kiện/ngoại lệ (`dieu_kien_ngoai_le`). Có 3 câu kiểm tra metadata filter (`q14`, `q15` thuộc dev; `q20` thuộc test). Toàn bộ 20 câu hỏi đều có `evidence_quote` được script `scripts/verify_benchmark.py` kiểm chứng tự động khớp 100% với văn bản trang nguồn.
- **Tiêu chí chọn chiến lược đã chốt trước khi xem test:**
  1. *Tiêu chí 1 (Bắt buộc):* Ưu tiên chiến lược có `Evidence Hit@3` trên tập `dev` cao nhất.
  2. *Tiêu chí 2:* Điểm `Chunk Coherence` trung bình (thang điểm 2) cao hơn (ít bị cắt cụt câu).
  3. *Tiêu chí 3:* `Hit@1` trên tập `dev` cao hơn khi điểm Hit@3 tương đương.
  4. *Tiêu chí 4:* Số lượng chunk và chi phí thấp hơn.

## Kết quả

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 7/15 (46.67%) | 11/15 (73.33%) | 215 | 5.61s | $0.00048 |
| A | test | 3/5 (60.00%) | 5/5 (100.00%) | 215 | - | - |
| B | dev | 10/15 (66.67%) | 13/15 (86.67%) | 191 | 3.37s | $0.00043 |
| B | test | 3/5 (60.00%) | 5/5 (100.00%) | 191 | - | - |
| C | dev | 10/15 (66.67%) | 13/15 (86.67%) | 191 | (Dùng B) | $0.00000 |
| C | test | 3/5 (60.00%) | 5/5 (100.00%) | 191 | (Dùng B) | $0.00000 |

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | 1.00 / 2.0 (n=10) | 15/15 (100%) | 3/3 (100%) | 0: 0, 1: 0, 2: 5 (2.00 / 2.0) |
| B | 1.80 / 2.0 (n=10) | 15/15 (100%) | 3/3 (100%) | 0: 0, 1: 0, 2: 5 (2.00 / 2.0) |
| C | 1.80 / 2.0 (n=10) | 15/15 (100%) | 3/3 (100%) | 0: 0, 1: 0, 2: 5 (2.00 / 2.0) |

Đường dẫn trace, nhãn thủ công và cách chọn mẫu:
- Trace toàn bộ 60 lượt truy xuất (20 câu hỏi × 3 chiến lược): [results/traces.json]
- Chấm thủ công Chunk Coherence trên 10 vị trí nguồn cố định (trang 19 đến 28): [results/manual_coherence.csv]
- Kiểm tra độ chính xác và tính tuân thủ Metadata trên 5 câu test × top-3: [results/manual_metadata_audit.csv]
- Chấm thủ công Grounding Quality trên 5 câu test: [results/manual_grounding.csv]

## Phân tích và kết luận

### 1. So sánh có kiểm soát A–B và B–C
- **So sánh A–B (Tác động của phương pháp chia chunk):**
  - **Retrieval Accuracy:** Trên tập `dev`, Chiến lược B vượt trội hoàn toàn so với A: `Hit@1` tăng từ **46.67% (7/15) lên 66.67% (10/15)**, `Evidence Hit@3` tăng từ **73.33% (11/15) lên 86.67% (13/15)**.
  - **Tính mạch lạc (Coherence):** Điểm Coherence của B đạt **1.80/2.0** so với **1.00/2.0** của A. Phương pháp cố định kích thước 500 ký tự thường xuyên cắt đứt ngang câu, tách rời mệnh đề điều kiện hoặc dòng lệnh khỏi phần giải thích ý nghĩa. Ngược lại, chunking theo đoạn văn bảo toàn toàn vẹn ngữ cảnh.
  - **Tài nguyên:** Chiến lược B chỉ tạo ra **191 chunks** (ít hơn A 24 chunks), giảm 11.2% số lượng vector cần lưu trữ và tiết kiệm thời gian ingest (3.37s so với 5.61s).
- **So sánh B–C (Tác động của Metadata Filter):**
  - Chiến lược B và C dùng chung 100% embedding và chunks. Trên câu hỏi `q20` thuộc tập test (hỏi về cấu hình hệ thống Git với filter `chapter: ch01_getting_started`), cả 3 chunk trả về của C đều tuân thủ 100% phạm vi Chương 1, loại bỏ hoàn toàn khả năng bị rò rỉ các đoạn văn nhắc tới file cấu hình ở các chương sau. Trên các câu hỏi dev có filter (`q14`, `q15`), Chiến lược C đảm bảo độ tin cậy tuyệt đối về mặt phạm vi tài liệu.

### 2. Hai ví dụ sai cụ thể (Failure Analysis)
- **Ví dụ 1 — Câu hỏi `q05` (Tập dev, Trang 38):**
  - *Câu hỏi:* *"In the short output format of git status, what do the two columns indicate?"*
  - *Evidence:* *"There are two columns to the output — the left- hand column indicates the status of the staging area and the right-hand column indicates the status of the working tree."*
  - *Chiến lược A (Thất bại - Hit@3 = False):* Do chia cứng 500 ký tự với overlap 50, đoạn văn này bị cắt làm đôi: phần mở đầu mô tả bảng ký hiệu nằm ở chunk trước (`A_progit-v2_p38_c001`), trong khi câu giải thích ý nghĩa 2 cột nằm ở chunk sau (`c002`). Vì câu hỏi chứa cụm từ *"short output format"*, embedding của A ưu tiên kéo về chunk chứa ví dụ terminal thay vì chunk chứa câu giải thích 2 cột, khiến cả top-3 của A đều trượt bằng chứng.
  - *Chiến lược B (Thành công - Hit Rank 3):* Chiến lược B gom toàn bộ đoạn giải thích và bảng ký hiệu vào một chunk trọn vẹn 544 ký tự (`B_progit-v2_p38_c001`), giúp giữ trọn vẹn ngữ cảnh và trúng bằng chứng ở Rank 3.
- **Ví dụ 2 — Câu hỏi `q15` (Tập dev, Trang 39):**
  - *Câu hỏi:* *"In nested .gitignore files, what is the scope of rules specified in those files?"*
  - *Evidence:* *"The rules in these nested .gitignore files apply only to the files under the directory where they are located."*
  - *Chiến lược A (Thất bại - Hit@3 = False):* Trang 39 có nhiều ví dụ cấu hình `.gitignore`. Do cửa sổ cố định 500 ký tự cắt cụt đoạn văn thành 3 mẩu rời rạc, embedding của A bị thiên lệch về các đoạn chứa cú pháp regex `*.a`, `!lib.a` thay vì đoạn ghi chú về nested gitignore.
  - *Chiến lược B & C (Thành công - Hit Rank 1):* Chunking theo đoạn văn bảo toàn nguyên vẹn khối thông tin về nested gitignore, giúp B và C đưa chunk này lên ngay vị trí Rank 1 với độ tương đồng Cosine vượt trội.

### 3. Chiến lược lựa chọn, đánh đổi và điều kiện áp dụng
- **Chiến lược được chọn:** **Chiến lược C (hoặc B với chế độ metadata filter chủ động)** là chiến lược tối ưu nhất.
  - Thỏa mãn toàn bộ 4 tiêu chí đã chốt trước khi xem test: `Evidence Hit@3` trên dev cao nhất (86.67%), `Coherence` cao nhất (1.80/2.0), `Hit@1` cao nhất (66.67%), và số lượng chunk ít hơn 11.2%.
- **Đánh đổi (Trade-offs):**
  - Chunking theo đoạn văn có thể tạo ra độ dài chunk dao động không đều (từ 36 ký tự đến 603 ký tự) so với kích thước đều tăm tắp của Fixed-size. Cần có thuật toán gộp các đoạn ngắn (như đã hiện thực trong code) để tránh các chunk rác.
  - Metadata filter yêu cầu phía Client/Agent phải biết trước hoặc suy luận chính xác bộ lọc ngữ cảnh. Nếu filter sai (ví dụ người dùng hỏi lệnh git basics nhưng gán nhầm filter `ch01`), hệ thống sẽ lọc bỏ mất đáp án đúng.
- **Điều kiện áp dụng:** Rất phù hợp cho các tài liệu có cấu trúc phân tầng rõ ràng (sách kỹ thuật, quy chế học vụ, sổ tay chính sách, tài liệu API nhiều phiên bản).

### 4. Hạn chế và Hướng cải tiến
- **Hạn chế:**
  - Tập test gồm 5 câu là kích thước mẫu nhỏ theo quy chuẩn của lab 4 giờ; kết quả test 100% Hit@3 là minh chứng khả quan nhưng chưa thể suy rộng cho toàn bộ các tình huống người dùng thực tế.
  - Đánh giá thủ công được thực hiện bởi tác giả báo cáo nên có thể tiềm ẩn thiên lệch cá nhân (mặc dù đã tuân thủ thang đo khách quan 0–2 có tiêu chí ranh giới rõ ràng).
- **Cải tiến nếu mở rộng (Hybrid Retrieval):**
  - Với các câu hỏi chứa định danh dòng lệnh chính xác như `git config --list --show-origin` hay cú pháp cờ `-p / --patch`, việc kết hợp **Dense Embedding (Cosine) với Sparse Keyword Search (BM25 / Reciprocal Rank Fusion)** sẽ giúp đẩy các kết quả từ Rank 2, Rank 3 lên thẳng Rank 1 tuyệt đối.
