# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

## Bảng phân tích chi tiết (Case C-002@11)

| Trường | Nội dung |
|---|---|
| **Trial** | `seeded_regression C-002@11`, Run ID: `R-seeded_regression-C-002-s11` trong `reports/eval_seeded_regression.json` |
| **Triệu chứng** | Grader `TrialPass`, `DbFactKept`, `RefundAmountCorrect` fail (`lab8 grader: FAIL (status resolved != denied)`). Reply nói *"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."* trong khi nhãn yêu cầu `status: denied` và `refund_vnd: 0`. |
| **Bước sai đầu tiên** | **Bước 3: event `model_override`** với payload `{"delay_days": 5}` |
| **Vì sao là bước *đầu tiên*** | Bước 1 (`handoff`) và Bước 2 (`investigator`) hoàn toàn đúng: điều tra viên tra cứu DB ra đơn hàng O-202 với sự thật khách quan `delay_days: 2`. Ở bước 3, agent đã tin vào nội dung khiếu nại của khách hàng trong ticket ("Đơn giao trễ 5 ngày") và đè sự thật của cơ sở dữ liệu (`model_override: delay_days = 5`). Các bước sai tiếp theo (bước 4 `quote` ra 20.000đ, bước 6 hoàn tiền và reply) đều là hệ quả tất yếu xuất phát từ bước 3. |
| **Failure mode** | **FM-03**: `ticket_trust` (Tin ticket hơn DB) |
| **Đối chứng** | Cùng `C-002@11` trên shape `fixed`: Bước 2 lấy `delay_days: 2` từ DB. Không có bước `model_override`. Bước 3 `quote` tính ra `amount_vnd: 0` (`no_entitlement`). Bước 4 trả lời từ chối hoàn tiền theo đúng chính sách (`status: denied`, `refund_vnd: 0`). |
| **Regression test** | Grader `DbFactKept` bắt event `model_override` (kiểm thử qua `test_override_event_breaks_db_fact` trong `src/tests/test_lab9_graders.py`), kết hợp với `RefundAmountCorrect`. Đã xác minh: fail trên `seeded_regression` và pass 100% trên `fixed`. |
| **Chưa chắc chắn** | Trace ghi nhận việc đè giá trị diễn ra sau khi model phân tích ticket, nhưng không thể hiện trọng số nội tại của LLM (nếu dùng model thật) vì bài lab chạy qua MockLLM theo quy tắc logic giả lập. |

---

## Chi tiết Trace đối chứng

### 1. `seeded_regression C-002@11` (Bản lỗi)
```
== seeded_regression C-002@11  lab8 grader: FAIL (status resolved != denied)
-- trace (step, kind, payload)
   1 handoff            {"contract_version": "handoff.v1", "task": "check_applicable_policy", ...}
   2 investigator       {"lookup_order": {"visible": true, "order": {"order_id": "O-202", "delay_days": 2, ...}}}
   3 model_override     {"delay_days": 5}                   <-- BƯỚC SAI ĐẦU TIÊN (FM-03)
   4 quote              {"amount_vnd": 20000, "reason": "entitled", "clause_ids": ["SHIP-LATE-03"]}
   5 refund_history     {"refund_count": 0, "refunded_vnd": 0}
   6 reply              {"text": "Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."}
-- ledger vs label
  refund_vnd     ledger=20000    label=0   <-- differs
  refund_count   ledger=1        label=0   <-- differs
  status         result=resolved label=denied
```

### 2. `fixed C-002@11` (Bản đối chứng chuẩn)
```
== fixed C-002@11  lab8 grader: PASS (ok)
-- trace (step, kind, payload)
   1 handoff            {"allowed_tools": ["lookup_order", ...], "claim_id": "C-002", ...}
   2 investigator       {"lookup_order": {"visible": true, "order": {"order_id": "O-202", "delay_days": 2, ...}}}
   3 quote              {"amount_vnd": 0, "reason": "no_entitlement", "clause_ids": [], "parts": {}}
   4 reply              {"text": "Dạ, đơn O-202 chưa đủ điều kiện hoàn theo chính sách hiện hành."}
-- ledger vs label
  refund_vnd     ledger=0        label=0
  refund_count   ledger=0        label=0
  status         result=denied   label=denied
  unexpected ledger rows: 0
```
