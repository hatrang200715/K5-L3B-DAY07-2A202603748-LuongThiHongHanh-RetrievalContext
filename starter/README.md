# Starter Day 7

| File | Công dụng |
|---|---|
| `agentic.py` | Khung agent ví dụ với số lượt search, top-k và context budget có thể cấu hình |
| `baseline.py` | TF-IDF lexical baseline, chạy offline |
| `convert_day6.py` | Chuyển một số trường JSON từ Day 6 |
| `agent_metrics.py` | Tổng hợp nhãn đánh giá do bạn tự chấm |

Starter **chưa phải solution hoàn chỉnh**. Bạn phải nối model và vector store thật, triển khai ít nhất 3 phương pháp retrieval do bạn chọn, gồm dense trên vector store Day 6. Mock chỉ dùng để test code.

## 1. Kết nối agent

Trong `agentic.py`, hiện thực:

- `Controller.decide`: gọi model thật và trả `{action: "search", query: "..."}` hoặc `{action: "answer", answer: "... [chunk-id]", citations: ["chunk-id"]}`.
- `Retriever.search`: tạo query embedding tương thích Day 6, truy vấn vector store thật và trả chunk theo [định dạng dữ liệu](../data/README.md).

Tự viết chương trình nối hai phần với `run_agent`, hoặc thay thế bằng kiến trúc nhiều tool. Tham số `max_searches`, `top_k` và `budget` chỉ là mặc định của ví dụ, không phải giới hạn của đề. Xem `tests/test_agentic.py` để hiểu cách gọi; kết nối trong test là mock. Khung code kiểm tra citation ID có trong context, nhưng bạn phải tự đọc xem nguồn có hỗ trợ câu trả lời. Báo lỗi kết nối, không thay bằng kết quả giả.

## 2. Chạy TF-IDF baseline

Chạy từ thư mục gốc với Python 3.11 trở lên:

```bash
python3 -m unittest discover -s tests -v
python3 starter/baseline.py --chunks data/example_chunks.json --questions data/example_questions.json --split dev --output starter/results/example-dev
```

Kết quả có `summary.json` và `traces.json`. Dữ liệu mẫu chỉ có một câu, không đủ để nộp bài. TF-IDF là lexical retrieval, không dùng filter và không thay dense retrieval.

## 3. Dùng dữ liệu Day 6

Xuất chunk và câu hỏi thành hai JSON array. Starter Day 6 không quy định tên bảng hay cách xuất; bạn cần tự thực hiện. Nếu chunk có `chunk_id`, `document_id`, `source`, `page`, `text`, `metadata` và câu hỏi có `gold_source_id`, `gold_page`, `evidence_quote`, chạy:

```bash
python3 starter/convert_day6.py --chunks <day6_chunks.json> --questions <day6_questions.json> --output starter/data/converted
python3 starter/baseline.py --chunks starter/data/converted/chunks.json --questions starter/data/converted/questions.json --split dev --output starter/results/dev-tfidf
```

Thay phần trong `< >` bằng đường dẫn thật. Script chỉ đổi tên trường, không tự truy cập database hay đoán evidence. Nếu cấu trúc khác, tự viết adapter. Đối chiếu lại nguồn, trang và evidence.

`--split dev` chỉ chấm dev. Sau khi chốt cấu hình, dùng `--split test` và chọn thư mục kết quả khác. Nếu test Day 6 từng dùng để chỉnh hệ thống, tạo test mới theo [GUIDE.md](../GUIDE.md). Baseline mẫu dùng evidence nằm trong một chunk và context từ top-3; cần mở rộng hoặc tự đánh giá nếu dùng multi-hop, context từ nhiều lượt hay schema khác. Khớp nguyên văn bằng code không thay thế đánh giá thủ công.

## 4. Tổng hợp đánh giá agent

Sau khi chạy agent thật và tự chấm, chuẩn bị ba JSON array:

- `cases.json`: mỗi câu có `id`, `split`, `answerable` (`true` nếu có đủ evidence).
- `traces.json`: mỗi kết quả có `query_id`, `status` (`answered`, `abstain`, `error`), `events`, `citations`. Thêm `query_id` vào kết quả `run_agent`; lỗi kết nối ghi riêng với `status: "error"`. Script đếm tool use qua event `search`: nếu dùng nhiều tool, chuẩn hóa mỗi lượt retrieval về event này và ghi tên tool trong trường khác, hoặc tự viết metric tương đương.
- `reviews.json`: mỗi nhãn có `query_id`, `citation_support` là danh sách đúng/sai ứng với từng citation. Câu có đáp án cần `answer_grade` 0–2 theo [BENCHMARK.md](../BENCHMARK.md); nếu bị từ chối, chấm 0. Câu thiếu evidence cần `abstention_correct` (`true`/`false`) do người chấm xác nhận. Lần chạy lỗi không cần nhãn.

```bash
python3 starter/agent_metrics.py --cases <cases.json> --traces <traces.json> --reviews <reviews.json> --split test --output starter/results/agent-test/summary.json
```

Thay đường dẫn trong `< >`. Script tổng hợp nhãn bạn đã chấm, không tự đánh giá nội dung. Mẫu số bằng 0 nghĩa là không áp dụng. Lỗi kết nối được báo riêng, không tính vào chất lượng; giữ trace và nhãn để đối chiếu.

## 5. Chạy agent thật trên benchmark Day 7

`run_day7_agent.py` kết nối OpenRouter với PostgreSQL/pgvector qua `starter/.env` và chạy bộ câu hỏi Day 7 trên các index `day7_A`, `day7_B`, `day7_C`. Mặc định chạy đủ 17 câu dev trên cả ba chiến lược. Model không nhận gold; chỉ chiến lược C áp dụng section filter có sẵn trong câu hỏi. Cần có `OPENROUTER_API_KEY`, `DATABASE_URL`, và embedding model tương thích với index trong `.env`. Sao chép [`.env.example`](.env.example) thành `.env` rồi điền giá trị; không commit `.env`.

Chạy từ thư mục `starter`:

```bash
.venv/bin/python run_day7_agent.py --model openai/gpt-4o-mini
```

Mỗi cấu hình dùng top-3, tối đa 4 lượt search, context budget mặc định 3.000 ký tự và temperature 0. Có thể đổi tham số bằng `--top-k`, `--max-searches`, `--budget-chars`; giữ giống nhau giữa các cấu hình để so sánh. Lệnh gọi API thật và có thể phát sinh phí. Output được ghi vào thư mục timestamp mới trong `starter/results/day7/`, gồm `traces.json`, `summary.json` và `run.json`; trace có truy vấn, kết quả retrieval, context, câu trả lời, citation, trạng thái, thời gian, token và chi phí do provider báo. Nếu provider không trả chi phí, trường thiếu được đếm riêng. Lỗi từng câu được ghi với trạng thái `error`, không thay bằng kết quả giả.

Các chỉ số trong summary là vận hành, không tự chấm độ đúng. Tự xem context, câu trả lời và từng citation; ghi nhãn grounded answer, citation support và abstention theo [BENCHMARK.md](../BENCHMARK.md). Chỉ chạy test sau khi đã chọn cấu hình trên dev.

Sau khi chọn cấu hình, có thể chạy baseline A và cấu hình chọn C trên cùng test:

```bash
.venv/bin/python run_day7_agent.py --model openai/gpt-4o-mini --split test --strategies A C
```

Benchmark Day 7 hiện đã chạy test cho retrieval/context; do đó test agent này là kết quả mô tả trên bộ đã lộ, không phải đánh giá độc lập mù.

## 6. Thử thách nâng cao: PDF và evidence trực quan

Benchmark riêng nằm trong `benchmark/advanced/`: `questions.json` có 18 câu dev và 30 câu test; đáp án/evidence được tách riêng trong `gold.json` và không được truyền vào runner. Test có 6 câu bảng, 5 ảnh/sơ đồ, 5 biểu đồ, 4 multi-hop, 4 text và 6 câu thiếu evidence. Dev có 15 câu có đáp án và 3 câu thiếu evidence. Dùng validator trước khi chạy:

```bash
.venv/bin/python validate_advanced_benchmark.py
```

Tạo lại index ảnh toàn bộ trang nội dung (cần PyMuPDF, khai báo trong `requirements.txt`). Manifest nguồn được commit tại [`benchmark/advanced/manifest.yaml`](benchmark/advanced/manifest.yaml); PDF không được commit, hãy đặt đúng tên file mặc định trong `data/`:

```bash
.venv/bin/python build_advanced_visual_index.py --manifest benchmark/advanced/manifest.yaml
```

Index lưu số trang PDF vật lý, hash PDF/ảnh và ảnh trang đầy đủ. Runner ghép ảnh của tối đa hai trang truy xuất vào câu hỏi bảng/biểu đồ/ảnh-sơ đồ/multi-hop; câu text và câu thiếu evidence không gửi ảnh. Đây không phải OCR hay image retrieval độc lập. Đối chiếu vùng/locator của gold với tài liệu gốc; validator tự động chỉ kiểm tra quote text trích được và cấu trúc benchmark, không xác nhận độ đúng của diễn giải hình.

Sau khi xác minh nguồn và có đủ API credit, so sánh cấu hình trên dev trước:

```bash
.venv/bin/python run_day7_agent.py --model openai/gpt-4o-mini --split dev --strategies A B C --questions benchmark/advanced/questions.json --visual-index results/day7/advanced_visual_index --max-searches 2 --budget-chars 1800
```

Chấm dev rồi freeze một cấu hình trước khi chạy test. Chỉ khi đã freeze, chạy đủ test bằng cấu hình đã chọn (thay `A` bằng cấu hình thực tế):

```bash
.venv/bin/python run_day7_agent.py --model openai/gpt-4o-mini --split test --strategies A --questions benchmark/advanced/questions.json --visual-index results/day7/advanced_visual_index --max-searches 2 --budget-chars 1800
```

Không chọn cấu hình dựa trên test. Lỗi, timeout hoặc không có kết quả tính là câu không đạt; cần chấm thủ công toàn bộ test, citation và evidence từ PDF gốc rồi báo n/N theo từng nhóm. Sau khi có nhãn audit, tổng hợp tỉ lệ đạt theo nhóm (câu có đáp án đạt khi `answer_grade` = 2 và mọi citation được hỗ trợ; câu thiếu evidence đạt khi từ chối đúng; lỗi tính không đạt và báo riêng):

```bash
.venv/bin/python advanced_metrics.py --questions benchmark/advanced/questions.json --cases <cases.json> --traces <traces.json> --reviews <reviews.json> --split test --output results/day7/advanced-metrics.json
```

Các lần chạy dev hiện lưu dưới `results/day7/agent_dev_20261116T152306Z/` và `results/day7/agent_dev_20261116T153851Z/`, nhưng OpenRouter trả HTTP 402 do thiếu credit, nên chưa freeze cấu hình và chưa chạy test advanced. Không công bố điểm hay bonus từ các lần chạy dở dang.

## Lưu ý

TF-IDF dùng cách tách từ đơn giản. `baseline.py` dùng mặc định context budget 800 ký tự, gồm cả nguồn; chunk không vừa bị bỏ. Bạn có thể chọn cách khác. File kết quả cùng tên sẽ bị ghi đè. `starter/data/` và `starter/results/` không được Git theo dõi mặc định; nếu được phép chia sẻ, dùng `git add -f <đường-dẫn>`, hoặc ghi cách tái tạo. Không nộp dữ liệu mật và secret.

Khung agent ưu tiên giữ chunk từ lần search trước. Khi chunk đầu chiếm gần hết budget, lần search sau có thể không thêm được evidence; hãy kiểm tra trace và thử cách chọn context phù hợp trên dev. Citation ID hợp lệ hoặc verifier trả “đúng” không đảm bảo câu trả lời được hỗ trợ; cần chấm thủ công.
