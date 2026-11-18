# Trace case: từ trace tới quyết định sai đầu tiên

Một case thật trong report `eval_seeded_regression.json`; không dùng dữ liệu Day8 của nhóm làm baseline.

```powershell
cd src
.\.venv\Scripts\python.exe -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
.\.venv\Scripts\python.exe -m lab9.trace_case --shape fixed --claim C-002 --seed 11
```

## Mẫu điền

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`; trial run `R-seeded_regression-C-002-s11`; eval run `E-seeded_regression-20261118-3a41` |
| Triệu chứng | Status resolved thay vì denied; ledger ghi 20.000 VND, nhãn 0; reply nói đã hoàn 20.000đ. Reply khớp ledger nhưng **cả quyết định lẫn ledger đều sai nghiệp vụ**. |
| Bước sai đầu tiên | Event **3**, `model_override`, payload `{"delay_days": 5}`; DB trong event 2 là 2 ngày. |
| Vì sao là bước đầu tiên | Event 1 handoff chỉ có tool đọc; event 2 tra đúng đơn visible và giữ delay_days = 2. Event 3 là nơi đầu tiên thay fact; event 4 quote sai là hậu quả. |
| Failure mode | FM-03 — ticket_trust |
| Đối chứng | Cùng C-002@11, `fixed` không có model_override, quote 0, denied, ledger 0. |
| Regression test | `tests/test_lab9_regression.py::test_lab9_trace_c002_rejects_ticket_override_and_accepts_fixed`; DbFactKept và RefundAmountCorrect False trên variant lỗi, True trên fixed; kiểm event 3, delay 5 và ledger 20.000/0. |
| Chưa chắc chắn | Trace cho thấy chuỗi dữ kiện và hành vi, không cho thấy reasoning nội bộ model. Host chặn approval nhưng không thay evaluator nghiệp vụ; approval hợp lệ vẫn có thể đi cùng quote sai. |

## Quy tắc

Đọc ledger trước reply. Không dùng exact-match câu trả lời: việc paraphrase hoặc thêm lookup hợp lệ không được biến thành regression. Case này được giữ như regression test riêng, không thêm nhãn inline hoặc âm thầm thay corpus v1. Các run/report trên được tạo trong môi trường trợ lý; chủ bài cần chạy lại trên máy và giải thích test trước khi nộp.
