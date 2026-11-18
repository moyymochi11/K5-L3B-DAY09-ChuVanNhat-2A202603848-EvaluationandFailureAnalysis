# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | ĐẠT (0.757 ≥ 0.6, 0.857 ≥ 0.8, 0.8 ≥ 0.7) | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | KHÔNG ĐẠT (κ = 0.375 < 0.6, R = 0.300 < 0.7) | loại |

---

## Phân tích Ma trận nhầm lẫn (Confusion Matrix)

### 1. `tone_ok` (`judge_tone_public.csv`)
- **Ma trận nhầm lẫn:** `{"tp": 24, "fp": 4, "fn": 6, "tn": 66}`
- Tỉ lệ lỗi quan sát: `0.280` $\rightarrow$ Tỉ lệ lỗi sau hiệu chỉnh (Rogan-Gladen): `0.300`
- Đánh giá: Độ thống nhất cao ($\kappa = 0.757$), cả Precision (0.857) và Recall (0.800) đều vượt sàn. Judge nhận diện tốt giọng điệu chuẩn mực và các trường hợp suồng sã.

### 2. `helpful` (`judge_helpful_public.csv`)
- **Ma trận nhầm lẫn:** `{"tp": 9, "fp": 0, "fn": 21, "tn": 70}`
- Tỉ lệ lỗi quan sát: `0.090` $\rightarrow$ Tỉ lệ lỗi sau hiệu chỉnh (Rogan-Gladen): `0.300`
- Đánh giá: Judge bị ảo tưởng nghiêm trọng bởi các câu xin lỗi lịch sự, văn mẫu dài dòng. Bỏ sót tới 21/30 trường hợp không hữu ích (`fn = 21`, Recall chỉ đạt 30.0%). Số ca lỗi thực tế gấp hơn 3 lần so với quan sát của judge (30% vs 9%).

---

## ≥5 case audit thủ công

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & Đề xuất sửa Rubric |
|---|---|---|---|---|---|
| 1 | `H-008` (tone) | PASS | FAIL | Người đúng | Câu văn: *"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."* Agent xưng hô suồng sã "em - anh", dùng khẩu ngữ "nha", từ mượn tiếng Anh "check" không phù hợp văn phong chăm sóc khách hàng chuyên nghiệp. **Sửa rubric tone**: bổ sung quy định cấm đại từ xưng hô thân mật suồng sã và khẩu ngữ địa phương. |
| 2 | `H-029` (tone) | PASS | FAIL | Người đúng | Câu văn: *"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."* Judge thấy có tiền tố "Dạ, vui lòng chờ" nên cho qua. Thực tế vế sau "không cần nhắn thêm" mang sắc thái cộc cằn, gạt bỏ khách hàng. **Sửa rubric tone**: cấm các câu mệnh lệnh mang tính xua đuổi, cộc cằn. |
| 3 | `H-042` (tone) | FAIL | PASS | Người đúng | Câu văn: *"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."* Judge phạt FAIL vì câu có thông báo mốc thời gian kỹ thuật 3-5 ngày. Thực tế câu văn rất chuẩn mực, lịch sự, đúng sự thật. **Sửa rubric tone**: làm rõ việc cung cấp mốc thời gian ước tính xử lý là hành vi hợp lệ, không tính là lỗi giọng điệu. |
| 4 | `H-070` (tone) | PASS | FAIL | Người đúng | Câu văn: *"Dạ, LogiX đã hoàn 90.000đ cho đơn O-909 ạ 😂😂"* Judge bỏ qua emoji. Thực tế việc dùng emoji cười lăn lộn (😂😂) trong văn cảnh hỗ trợ xử lý sự cố đơn hàng là phản cảm, thiếu nghiêm túc. **Sửa rubric tone**: cấm hoàn toàn emoji không phù hợp hoặc cấm emoji cợt nhả. |
| 5 | `HL-016` (helpful) | PASS | FAIL | Người đúng | Câu văn: *"Dạ, LogiX thành thật xin lỗi anh/chị vì sự bất tiện này và rất trân trọng sự kiên nhẫn của anh/chị. LogiX đã hoàn 55.000đ cho đơn O-404. Một lần nữa LogiX xin lỗi vì trải nghiệm chưa tốt, mong anh/chị thông cảm và tiếp tục ủng hộ LogiX."* Câu văn lặp đi lặp lại văn mẫu xin lỗi máy móc 2 lần. Judge bị đánh lừa bởi độ dài và sự lễ phép. **Sửa rubric helpful**: phạt nặng các câu lặp văn mẫu, spam lời xin lỗi sáo rỗng gây ức chế cho khách hàng. |
| 6 | `HL-047` (helpful) | PASS | FAIL | Người đúng | Câu văn: *"Ok bạn, đơn O-515 xử lý rồi nhé."* Judge cho PASS vì ngắn gọn. Thực tế câu trả lời vô dụng (unhelpful): không cho biết đã xử lý thế nào, hoàn tiền bao nhiêu, hoàn qua đâu hay bị từ chối. **Sửa rubric helpful**: yêu cầu bắt buộc phải nêu rõ kết quả nghiệp vụ cụ thể (số tiền/hành động). |

---

## Kết luận
- **Tiêu chí bị loại:** `helpful` bị loại hoàn toàn khỏi các release gate. Lý do: Cohen's $\kappa = 0.375$ (thấp hơn nhiều so với ngưỡng tối thiểu 0.6) và Recall chỉ đạt $0.300$ (bỏ sót 70% số ca vi phạm). Ma trận nhầm lẫn cho thấy $FN = 21$, trong khi $TP = 9$, chứng tỏ LLM judge bị thiên kiến bởi sự lễ phép bề ngoài (sycophancy / verbosity bias).
- **Tiêu chí được chấp nhận:** `tone_ok` đạt chuẩn ($\kappa = 0.757 \ge 0.6, P = 0.857 \ge 0.8, R = 0.800 \ge 0.7$), có thể dùng làm tín hiệu cảnh báo văn phong.
- **Rủi ro còn lại:** Cả hai tập đánh giá hiện tại chỉ là dữ liệu replay công khai; trong môi trường sản xuất thực tế cần liên tục thu thập mẫu hội thoại người dùng thật (production traffic) và gán nhãn thủ công định kỳ để có tập held-out test độc lập, chống hiện tượng data drift và overfitting rubric.
