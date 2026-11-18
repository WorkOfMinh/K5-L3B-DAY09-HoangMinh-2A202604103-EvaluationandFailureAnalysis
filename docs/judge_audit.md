# Judge audit

Chạy `python -m lab9.judge --csv <file> --audit 5`. FAIL là positive class: judge phải tìm được lỗi, không chỉ ít báo nhầm.

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.8 | có | dùng giới hạn cho tone, không chấm tiền |
| helpful | 100 | 0.375 | 1.0 | 0.3 | không | loại khỏi gate |

## ≥5 case audit thủ công

Đối chiếu nhãn người **được cung cấp** và note trong CSV; đây là audit của trợ lý dựa trên rubric/data, không giả làm đợt tuyển người gán nhãn mới.

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / hành động sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 | PASS | FAIL | Theo nhãn người đã cấp | xưng 'em' + 'nha', quá suồng sã với khách; judge coi là thân thiện; Nhãn người; quy định mức trang trọng, xưng em/nha không mặc định thân thiện phù hợp. |
| 2 | H-017 | PASS | FAIL | Theo nhãn người đã cấp | xưng 'bạn' với khách lớn tuổi; judge coi là thân thiện; Nhãn người theo bối cảnh note; kiểm cách xưng hô, không tự suy tuổi chỉ từ reply. |
| 3 | H-029 | PASS | FAIL | Theo nhãn người đã cấp | giọng ra lệnh ('không cần nhắn thêm'); judge chỉ thấy 'Dạ, vui lòng'; Nhãn người; đánh giá cả câu ra lệnh, không chỉ đếm từ Dạ/vui lòng. |
| 4 | H-042 | FAIL | PASS | Theo nhãn người đã cấp | ngắn nhưng đủ ý; judge phạt vì 'thiếu xin lỗi'; Nhãn người; không bắt buộc xin lỗi khi đã đủ thông tin và lịch sự. |
| 5 | H-051 | FAIL | PASS | Theo nhãn người đã cấp | dùng từ 'refund' — CS LogiX cho phép; judge phạt vì tiếng Anh; Nhãn người; cho phép thuật ngữ refund theo rubric CS, không loại chỉ vì có tiếng Anh. |
| 6 | HL-015 | PASS | FAIL | Theo ledger trong note | sai tiền: ledger ghi 40.000đ; chuyển kiểm số tiền sang ReplyAmountCorrect, không thưởng độ dài/xin lỗi thay cho facts. |
| 7 | HL-016 | PASS | FAIL | Theo ledger trong note | sai tiền: ledger ghi 35.000đ; chuyển kiểm số tiền sang ReplyAmountCorrect, không thưởng độ dài/xin lỗi thay cho facts. |
| 8 | HL-020 | PASS | FAIL | Theo ledger trong note | sai tiền: ledger ghi 120.000đ; chuyển kiểm số tiền sang ReplyAmountCorrect, không thưởng độ dài/xin lỗi thay cho facts. |
| 9 | HL-028 | PASS | FAIL | Theo ledger trong note | sai tiền: ledger ghi 35.000đ; chuyển kiểm số tiền sang ReplyAmountCorrect, không thưởng độ dài/xin lỗi thay cho facts. |
| 10 | HL-035 | PASS | FAIL | Theo ledger trong note | sai tiền: ledger ghi 35.000đ; chuyển kiểm số tiền sang ReplyAmountCorrect, không thưởng độ dài/xin lỗi thay cho facts. |

## Kết luận

- Tone: TP=24, FP=4, FN=6, TN=66. Observed failure rate 0.28; Rogan–Gladen hiệu chỉnh thành 0.30 với sensitivity=0.8, specificity=66/70. Dùng trong phạm vi tone sau khi sửa rubric và calibration lại trên nhãn mới; không tự động thay metric tiền bằng judge.
- Helpful: TP=9, FP=0, FN=21, TN=70. Precision=1.0 nhưng recall=0.3, κ=0.375: bỏ sót 21/30 lỗi. Không được dùng làm release gate chỉ vì precision cao. Observed 0.09 được hiệu chỉnh thành 0.30; RG không chữa được classifier bỏ sót hay thay kiểm tra từng claim.
- Nếu κ không xác định (hai bên đều constant), calibration phải FAIL. RG yêu cầu sensitivity + specificity > 1, clip kết quả về [0,1].
- Các hành động ở bảng là đề xuất sửa rubric; CSV replay không được sửa, nên **chưa có số liệu sau sửa rubric**. Không dùng tone/helpful làm blocking metric trong spec tiền hiện tại.
- Rủi ro còn lại: CSV công khai/replay, synthetic, không held-out thật. Cần người gán nhãn mới, blind audit, dữ liệu/phiên bản judge mới và calibration lại trước khi dùng ngoài pilot.

Nguồn số liệu: `src/reports/day09_evidence.json` do `scripts/day09_evidence.py` sinh; hai CSV gốc không đổi.
