# Báo cáo Day 7

## Dữ liệu và benchmark

- Nguồn, quyền sử dụng, số trang và số chunk: 

UNICEF/UNI930171/Luu Thu Huong (https://www.unicef.org/vietnam/vi/bao-cao/tam-nhin-phat-trien-toan-dien-tre-em-2045), PDF có 136 trang vật lý; manifest tính 107 trang nội dung: trang PDF 9–14, 16–114 và 134–135. Số trang evidence dùng số trang PDF vật lý. Chi tiết ở manifest.

Metadata: /starter/results/day7

- Vector store, embedding model, phiên bản và số chiều:

B và C dùng chung chunk/vector; C lọc theo section khi truy vấn. 

Embedding model: openrouter:openai/text-embedding-3-small (1536 dimensions).
Indexed pgvector: day7_A: 631 chunks.
Indexed pgvector: day7_B: 548 chunks.
Indexed pgvector: day7_C: 548 chunks.

| Phương pháp | Cách chia chunk | Lọc metadata | Vai trò |
|---|---|---|---|
|A — Fixed-size|700 ký tự, overlap 100|Không lọc|Baseline|		
|B — Paragraph|Theo đoạn, tối đa 700 ký tự|Không lọc|So sánh ảnh hưởng của cách chia chunk với A|
|C — Paragraph + filter|Giống B	Lọc section khi câu hỏi có nêu phạm vi	|So sánh tác động của metadata |filter với B|

Đã chạy retrieval/context cho 24 câu hỏi × 3 phương pháp = 72 trace. Các chỉ số dưới đây chỉ tính trên câu có đáp án (15 dev, 5 test):

| Phương pháp | Split | Lọc Hit@1 | Evidence Hit@3 | Context Evidence Rate |
|---|---|---|---|---|	
|A — fixed-size|Dev|9/15|12/15|12/15|
|A — fixed-size|Test|4/5|5/5|5/5|
|B — theo đoạn|Dev|6/15|9/15|9/15|
|B — theo đoạn|Test|2/5|2/5|2/5|
|C — theo đoạn + filter|Dev|8/15|10/15|10/15|
|C — theo đoạn + filter	Test|2/5|2/5|2/5|

Context dùng toàn bộ top-3 theo format hiện tại của chatbot, không rerank hay cắt theo token. Vì vậy CER trùng Evidence Hit@3. Độ dài context trung bình lần lượt Dev/Test: A 2.136/2.183 ký tự; B 2.170/2.223; C 2.147/2.206. Filter của C tuân thủ trên 15/15 câu dev và 5/5 câu test có đáp án và filter.

- Agent model, cách chạy và phân chia dev/test:


- Cách xác định câu có/thiếu evidence và tiêu chí chấm:

## Retrieval và thử nghiệm

Thử nghiệm retrieval dùng cùng PDF snapshot, embedding `openai/text-embedding-3-small` (1536 chiều), PostgreSQL 16 + pgvector (cosine), cùng 24 câu hỏi và top-3. A là baseline fixed-size 700 ký tự/overlap 100; B đổi sang paragraph-aware (tối đa 700 ký tự); C dùng chunk/vector của B và chỉ áp dụng section filter nếu câu hỏi nêu rõ phạm vi. Không có rerank. Retrieval/context đưa đủ top-3 vào formatter hiện tại, kèm nhãn trang/section; không cắt context. CER vì vậy trùng Evidence Hit@3. Với agent, context tích lũy tối đa 3.000 ký tự, tối đa 4 lượt search. Các số giây/USD dưới đây là toàn bộ lần chạy agent tương ứng, không phải thời gian/chi phí retrieval thuần; chi phí là số provider báo.

| Cấu hình | Phương pháp, top-k, filter, rerank, context budget | Giả thuyết / thay đổi | Split | Hit@1 | Evidence Hit@3 | Context Evidence Rate | Thời gian / chi phí |
|---|---|---|---|---:|---:|---:|---|
| A — baseline | Fixed-size 700 ký tự, overlap 100; top-3; không filter/rerank; context retrieval đủ top-3 | Mốc so sánh | Dev | 9/15 (60%) | 12/15 (80%) | 12/15 (80%) | Agent: 129.86 giây / $0.005690 |
| B — paragraph | Paragraph tối đa 700 ký tự; top-3; không filter/rerank; context đủ top-3 | Đo tác động của paragraph chunking so với A | Dev | 6/15 (40%) | 9/15 (60%) | 9/15 (60%) | Agent: 140.62 giây / $0.006538 |
| C — paragraph + filter | Như B; top-3; section filter chỉ khi câu hỏi nêu; không rerank; context đủ top-3 | Đo tác động của metadata filter so với B; đây cũng là cải thiện được thử | Dev | 8/15 (53.3%) | 10/15 (66.7%) | 10/15 (66.7%) | Agent: 116.11 giây / $0.005666 |
| C — cấu hình chọn | Như trên; agent context tối đa 3.000 ký tự, tối đa 4 search | Chạy test sau khi chọn trên dev; kết quả test chỉ mang tính mô tả vì split đã lộ | Test | 2/5 (40%) | 2/5 (40%) | 2/5 (40%) | Agent: 64.50 giây / $0.003259 |
| A — baseline | Như A; agent context tối đa 3.000 ký tự, tối đa 4 search | Đối chứng test với cấu hình chọn | Test | 4/5 (80%) | 5/5 (100%) | 5/5 (100%) | Agent: 47.60 giây / $0.002281 |

Không chạy hai cấu hình cải thiện độc lập khác; C đồng thời là phương pháp paragraph và phép thử filter, không gán kết quả cho các thử nghiệm chưa chạy. Trên dev, A và C cùng có 13/17 lượt agent trả lời, không lỗi; C nhanh hơn và rẻ hơn nhẹ. Khi chấm nội dung, C trả lời đúng D7-03, D7-06, D7-15 mà A từ chối hoặc trả sai; C cũng từ chối đúng D7-22, câu A khẳng định số tiền không được báo cáo. Do đó chọn C trên dev, không dựa vào test. Hai lỗi dev tiêu biểu: (1) A trả sai D7-15 do lấy đoạn trang 91 nói về chỉ số bạo lực khác; thử filter section ở C đưa evidence cross-cutting đúng tại trang 100 và câu trả lời đúng. (2) A diễn giải số tiền/model benefit gần D7-22 thành cam kết tương lai; C abstain vì không có evidence về số tiền cam kết. C vẫn từ chối nhầm D7-07 và D7-10, nên filter chưa khắc phục được mọi lỗi retrieval.

Các cấu hình chỉ so sánh trên cùng split; test không được dùng để chọn hay tinh chỉnh. Trên 5 câu test có đáp án, A đạt 5/5 câu có evidence trong top-3 và grounded answer 5/5; C đạt 2/5 retrieval evidence và 3/5 grounded answer. Cả hai từ chối đúng 2/2 câu thiếu evidence. Đây là kết quả mô tả trên test đã lộ, không phải đánh giá độc lập mù; cần benchmark test mới cho so sánh sau này.

## Agent và đánh giá

- Agent model và thiết lập: OpenRouter `openai/gpt-4o-mini`, temperature 0, tối đa 700 output tokens; embedding `openai/text-embedding-3-small` (1536 chiều); PostgreSQL 16 + pgvector, cosine. Tool `search` truy vấn top-3; chỉ C áp dụng section filter do câu hỏi cung cấp. Model nhận context tích lũy tối đa 3.000 ký tự, tối đa 4 lượt search, rồi gọi `final_answer` hoặc từ chối. Test đã được chạy trước cho retrieval/context, vì vậy kết quả test agent dưới đây là mô tả trên test đã lộ, không phải đánh giá độc lập mù.

- Chọn C trên dev: A và C đều có 13/17 lượt agent trả lời và không có lỗi; C mất 116.1 giây, chi phí $0.00567, so với A 129.9 giây và $0.00569. Khi đọc câu trả lời dev, C trả lời đúng D7-03, D7-06 và D7-15 mà A từ chối hoặc trả sai; C cũng từ chối D7-22 thiếu bằng chứng trong khi A khẳng định số tiền không có trong báo cáo. Hai giả thuyết/lỗi đã đối chiếu: (1) A trả sai D7-15 vì truy xuất đoạn trang 91 với một chỉ số bạo lực khác; filter section của C lấy đúng evidence cross-cutting trang 100 và trả lời đúng. (2) A diễn giải số tiền/model benefit gần câu D7-22 thành cam kết tương lai; C abstain đúng do không có bằng chứng về số tiền cam kết. C vẫn từ chối nhầm D7-07 và D7-10 trên dev, cho thấy filter không khắc phục được mọi retrieval miss. Không chỉnh cấu hình theo kết quả test.

- Cách xác định câu có/thiếu evidence và tiêu chí chấm: theo gold benchmark, đối chiếu context cuối và từng citation với evidence trong PDF; answerable chấm 0/1/2, context chấm 0/1/2, câu thiếu evidence kiểm tra agent có từ chối và không bịa thêm hay không.

- Tool, số lượt gọi, điều kiện dừng, cách chọn context và xử lý lỗi: `search` cho đến khi model gọi `final_answer` hoặc đạt tối đa 4 lượt; context tích lũy và đóng gói theo thứ tự candidate, top-3 mỗi lượt, budget 3.000 ký tự. Lỗi API/vector store ghi riêng, không dùng mock.

Kết quả chạy agent thật trên dev:

| Cấu hình | Trả lời / từ chối / lỗi | Retrieval calls | Thời gian | Chi phí provider |
|---|---:|---:|---:|---:|
| A — baseline | 13 / 4 / 0 trên 17 | 29 | 129.86 giây | $0.005690 |
| B — paragraph | 11 / 5 / 1 trên 17 | 35 | 140.62 giây | $0.006538 |
| C — paragraph + filter, chọn | 13 / 4 / 0 trên 17 | 29 | 116.11 giây | $0.005666 |

Test có 5 câu trả lời được và 2 câu thiếu evidence. Đã đọc cả 5 câu trả lời được và cả hai câu thiếu evidence cho baseline A và cấu hình C; chấm nội dung, context cuối gửi model, và từng citation so với đoạn được trích:

| Cấu hình / split | Tool use | Số lượt gọi | Grounded answer 0/1/2 và trung bình | Citation hợp lệ | Câu có citation | Abstention đúng | Từ chối nhầm |
|---|---|---|---|---|---|---|---|
| A — baseline / test | 7/7 (100%) | 5 câu × 1; 2 câu × 4 (13 lượt) | 0: 0, 1: 0, 2: 5; **2.00/2** | 5/5 | 5/5 câu trả lời | 2/2 | 0/5 |
| C — chọn / test | 7/7 (100%) | 3 câu × 1; 4 câu × 4 (19 lượt) | 0: 2, 1: 0, 2: 3; **1.20/2** | 3/3 | 3/3 câu trả lời | 2/2 | 2/5 |

Điểm context cho 5 câu có đáp án: A có mức 0: 0, 1: 0, 2: 5; C có mức 0: 2, 1: 0, 2: 3. Context D7-16 của C có chủ đề child labour nhưng không chứa xu hướng khảo sát được hỏi (con số 5.4% trong context là thống kê khác); D7-20 không có target 0.75–0.80. Mọi citation được chấm đều có trong context cuối và hỗ trợ câu trả lời. Với câu thiếu evidence, cả A và C đều tìm kiếm rồi từ chối, không nêu thêm khẳng định.

| Query ID | Loại câu | Tool call và kết quả | Câu trả lời và citation | Nhãn, lý do |
|---|---|---|---|---|
| D7-16 | Trend, có đáp án | A: 1 search; C: 4 search. | A: đúng 9.6% (2012), 5.4% (2018), 1.31% (2023), `unicef-vietnam-2045-children-p90-fixed-0003`. C: từ chối. | A context 2, answer 2; citation hỗ trợ cả ba tỷ lệ. C context 0 (chỉ có thống kê child labour khác), answer 0. |
| D7-17 | Direct, có đáp án | A: 1 search; C: 1 search. | Cả hai: 17.0% xuống 12.7%; A `unicef-vietnam-2045-children-p84-fixed-0000`, C `unicef-vietnam-2045-children-p84-paragraph-0000`. | Cả hai context 2, answer 2; citation hỗ trợ mức giảm. |
| D7-18 | Direct, có đáp án | A: 1 search; C: 1 search. | Cả hai: điểm 6.8, hạng 37; A `unicef-vietnam-2045-children-p105-fixed-0004`, C `unicef-vietnam-2045-children-p105-paragraph-0004`. | Cả hai context 2, answer 2; citation hỗ trợ điểm và thứ hạng. |
| D7-19 | Comparison, có đáp án | A: 1 search; C: 1 search. | Cả hai: hộ nghèo 50%, hộ giàu 17% ở tuổi 15; A `unicef-vietnam-2045-children-p106-fixed-0001`, C `unicef-vietnam-2045-children-p106-paragraph-0001`. | Cả hai context 2, answer 2; citation hỗ trợ cả hai nhóm và mốc tuổi. |
| D7-20 | Direct, có đáp án | A: 1 search; C: 4 search. | A: HCI 0.75–0.80, `unicef-vietnam-2045-children-p113-fixed-0002`. C: từ chối. | A context 2, answer 2. C context 0 (không có target), answer 0. |
| D7-23 | Thiếu evidence | Cả A và C: 4 search rồi từ chối. | Không câu trả lời khẳng định, không citation. | Abstention đúng 2/2 theo ghi chú kiểm tra toàn tài liệu của benchmark. |
| D7-24 | Thiếu evidence | Cả A và C: 4 search rồi từ chối. | Không câu trả lời khẳng định, không citation. | Abstention đúng 2/2 theo ghi chú kiểm tra toàn tài liệu của benchmark. |

- Tổng thời gian/chi phí test: A 47.60 giây / $0.002281; C 64.50 giây / $0.003259; không có lỗi provider/vector store. A dùng 12,473 prompt và 710 completion tokens; C dùng 18,832 prompt và 761 completion tokens. Lệnh: `cd starter && .venv/bin/python run_day7_agent.py --model openai/gpt-4o-mini --split test --strategies A C`.
- Trace, cấu hình, nhãn chi tiết và metrics: [`starter/results/day7/agent_test_20261116T123241Z/`](../../starter/results/day7/agent_test_20261116T123241Z/), gồm `traces.json`, `run.json`, `cases.json`, `reviews_A.json`, `reviews_C.json`, `metrics_A.json`, `metrics_C.json`. Dev traces: [`starter/results/day7/agent_dev_20261116T111804Z/`](../../starter/results/day7/agent_dev_20261116T111804Z/).
- Kết quả test mô tả cho thấy A tốt hơn C trên 5 câu có đáp án (5/5 so với 3/5), còn tỷ lệ từ chối đúng hai câu thiếu bằng chứng bằng nhau. Đây không phải cơ sở để đổi lựa chọn sau khi xem test; cần bộ test mới nếu muốn tối ưu hay chọn lại cấu hình. Chi phí do OpenRouter báo, không tính phần đánh giá thủ công.

## Thử thách nâng cao

- **Trạng thái: chưa hoàn thành; không nhận bonus.** Đã dựng visual page index và benchmark đủ kích thước, nhưng không thể chốt cấu hình dev hoặc chạy/chấm test vì OpenRouter hết credit (HTTP 402). Không có điểm advanced; các lỗi provider không được tính là chất lượng mô hình.

- Tài liệu, nguồn, quyền sử dụng, số trang và phiên bản: UNICEF Viet Nam, *Children at the Heart of Viet Nam's New Era: A Comprehensive Vision for Children's Development Towards 2045*, bản PDF truy cập ngày 2026-11-16, 136 trang vật lý. Nguồn gốc: [UNICEF Viet Nam](https://www.unicef.org/vietnam/vi/media/19741/file/Final%20-%20Designed%20Viet%20Nam%202045%20Full%20Report-En.pdf.pdf). SHA-256 snapshot `1dc94fe84874fdf0f0955d523990a019d116cbdd752fdfd1f6cc021a428dbdd9`. Manifest tính 107 trang nội dung (PDF 9–14, 16–114, 134–135); trang bìa/front matter, trang chia phần, tài liệu tham khảo và trang liên hệ bị loại có ghi lý do tại [manifest](../../starter/data/day7/manifest.yaml). UNICEF-hosted; chưa xác nhận giấy phép tái phân phối mở. Chỉ giữ bản cục bộ để chạy, không đưa PDF vào kết quả nộp.

- Cách xử lý nội dung: text được trích bằng `pypdf` và index vào pgvector cosine với embedding `openai/text-embedding-3-small` (1536 chiều); các index A/B/C giữ nguyên cấu hình Day 7. Đã tạo [visual page index](../../starter/results/day7/advanced_visual_index/index.json) cho đủ 107 trang nội dung: ảnh trang đầy đủ ở scale 1.2, số trang PDF vật lý, SHA-256 ảnh và hash PDF nguồn. Runner nối trang ảnh với các trang chunk được truy xuất và gửi tối đa hai ảnh cho câu hỏi bảng/biểu đồ/ảnh-sơ đồ/multi-hop; text-only/abstention không gửi ảnh. Đây là hỗ trợ vision theo trang truy xuất, không phải image retrieval/OCR độc lập; chưa lưu crop/bounding box. Các vùng cần kiểm tra được mô tả bằng locator trong gold nhưng phải đối chiếu thủ công bản gốc. Chi tiết index: [visual index](../../starter/results/day7/advanced_visual_index/index.json); ingest/vector config: [ingest metadata](../../starter/results/day7/ingest_metadata.json).

- Benchmark advanced riêng đã được tạo, gold tách khỏi câu hỏi chạy model: dev 18 câu (15 có đáp án, 3 thiếu evidence); test 30 câu (24 có đáp án, 6 thiếu evidence). Test có 6 bảng, 5 ảnh/sơ đồ, 5 biểu đồ, 4 multi-hop, 4 text và 6 thiếu evidence. [Validator](../../starter/validate_advanced_benchmark.py) xác nhận số lượng/ID, nguồn PDF 136 trang và 33 quote text; quote/cell/visual locator vẫn cần người chấm xác minh với bản gốc. Gold ghi rõ expected answer, trang, loại evidence, locator và rationale/terms cho các câu thiếu evidence. Toàn bộ câu thiếu evidence chưa hoàn tất rà soát thủ công độc lập trên mọi trang.

- Chạy dev nâng cao: model `openai/gpt-4o-mini`; lần đầu top-3, tối đa 4 search, budget 3.000 ký tự. A: 4 answered/14 lỗi; B: 2 answered/16 lỗi; C: 1 answered, 2 abstain, 15 lỗi. Provider báo HTTP 402 `in_flight_budget_exhausted`; chi phí provider báo tổng cộng $0.08157891. Lần thử lại tiết kiệm hơn (tối đa hai ảnh phù hợp với nhóm câu hỏi, tối đa 2 search, budget 1.800 ký tự) chỉ có A 3 answered/15 lỗi; B và C 18/18 lỗi, cùng HTTP 402 `openrouter_credits`; chi phí provider báo $0.02370425. Tổng chi phí hai lần chạy theo provider là $0.10528316. Trace đầy đủ: [dev lần 1](../../starter/results/day7/agent_dev_20261116T152306Z/) và [dev lần 2](../../starter/results/day7/agent_dev_20261116T153851Z/). Các câu lỗi không có kết quả và không được xem là trả lời sai/đúng; số câu chạy được cũng chưa được người chấm đánh giá. Vì lỗi API, chưa chọn/freeze cấu hình từ dev.

| Nhóm test advanced | Đã chạy / tổng | Tỷ lệ | Trạng thái |
|---|---|---|---|
| Bảng | 0/6 | Chưa tính | Test chưa chạy. |
| Ảnh, sơ đồ | 0/5 | Chưa tính | Test chưa chạy. |
| Biểu đồ | 0/5 | Chưa tính | Test chưa chạy. |
| Multi-hop | 0/4 | Chưa tính | Test chưa chạy. |
| Text | 0/4 | Chưa tính | Test chưa chạy. |
| Thiếu bằng chứng | 0/6 | Chưa tính | Test chưa chạy; kiểm tra thủ công absence cũng chưa xong. |
| **Toàn bộ** | **0/30** | **Chưa có điểm** | Chưa có cấu hình được freeze; không thể kết luận đạt ngưỡng 90% hoặc nhận bonus. |

- Lần chạy dev đầu ghi tổng khoảng 241.6 giây thời gian cấu hình (không tính riêng thời gian chuẩn bị); lần thử lại khoảng 36.1 giây. Không có test trace/review/metrics advanced vì không gọi test trước khi freeze cấu hình. Chi phí trên là phần OpenRouter báo cho các lần dev bị lỗi, không phải chi phí benchmark hoàn chỉnh.
- Cách tái lập và phần còn thiếu: [questions.json](../../starter/benchmark/advanced/questions.json), [gold.json](../../starter/benchmark/advanced/gold.json), [visual index builder](../../starter/build_advanced_visual_index.py), [runner](../../starter/run_day7_agent.py). Sau khi có API credit, chạy lại toàn bộ dev, chấm dev và freeze cấu hình; rà soát thủ công mọi câu thiếu evidence; chạy toàn bộ 30 câu test đúng một lần, chấm từng câu theo bản gốc và cập nhật metrics/lý do/lỗi/thời gian/chi phí. Chưa chạy test nên không dùng các kết quả test agent cơ bản đã lộ để chọn cấu hình advanced.
