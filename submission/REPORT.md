# Báo cáo Day 09 — Đặng Thị Vân Ly, 2A202603315

## 1. Kết luận trước

Pipeline kết luận Release. Đã quét 224 ảnh, loại 31 ảnh và xuất 193 ảnh vào submission/export/clean_v1. Người duyệt đã xem 80 ảnh. Sau duyệt còn cảnh báo ở 13/193 ảnh (6,7%), không còn lỗi bắt buộc; tỉ lệ cảnh báo thấp hơn ngưỡng Hold 10%.

## 2. Lỗi và phân việc

Số dưới đây là số issue trong báo cáo v1, không phải số ảnh duy nhất.


| Mã lỗi               | Số issue | Ai xử lý | Vì sao                                        |
| ---------------------- | --------: | ---------- | ---------------------------------------------- |
| `BAD_CLASS_ID`         |         6 | Máy       | Xóa dòng có ID lớp không hợp lệ         |
| `BAD_CLASS_NAME`       |         2 | Máy       | Sửa tên lớp theo cấu hình                 |
| `BAD_FORMAT`           |         3 | Máy       | Xóa dòng sai định dạng                    |
| `BAD_SIZE`             |         3 | Máy       | Loại ảnh quá nhỏ                           |
| `BOX_HUGE`             |         3 | Người    | Xem lại box phủ phần lớn ảnh              |
| `BOX_OUT_OF_IMAGE`     |         8 | Máy       | Cắt box vào trong ảnh                       |
| `BOX_TINY`             |         6 | Người    | Xem lại box quá nhỏ                         |
| `BOX_ZERO`             |         4 | Máy       | Xóa dòng có box rỗng                       |
| `CLASS_RARE`           |         4 | Người    | Xem xét lớp có quá ít box                 |
| `CORRUPT_IMAGE`        |         2 | Máy       | Loại ảnh hỏng                               |
| `DUP_BOX`              |         7 | Máy       | Xóa dòng box trùng                          |
| `DUP_IMAGE_EXACT`      |         8 | Máy       | Loại ảnh trùng từng byte                   |
| `DUP_IMAGE_NEAR`       |         7 | Máy       | Loại ảnh trùng gần đúng                  |
| `EMPTY_LABEL`          |        11 | Người    | Xác nhận ảnh nền hay thiếu nhãn          |
| `LEAK_TEST`            |        11 | Máy       | Loại ảnh trùng tập test/val                |
| `MISSING_LABEL_FILE`   |         6 | Người    | Gán nhãn vì máy không thể tự bịa nhãn |
| `POSSIBLE_FALSE_POS`   |        28 | Người    | Kiểm tra box có thể bị gán thừa          |
| `POSSIBLE_LOOSE_BOX`   |        11 | Người    | Kiểm tra box có thể lỏng hoặc lệch       |
| `POSSIBLE_MISSING`     |        32 | Người    | Kiểm tra vật thể có thể bị thiếu nhãn  |
| `POSSIBLE_WRONG_CLASS` |        13 | Người    | Kiểm tra nhãn có thể sai lớp              |

Hàng đợi có 98 ảnh và xếp theo mức ưu tiên tổng hợp từ các lỗi, đặc biệt lỗi ngữ nghĩa và lỗi cần người gán nhãn. Ảnh đầu hàng `img_0020` có `FIXED_DROP_LINE`, `POSSIBLE_MISSING` và `POSSIBLE_WRONG_CLASS`. Với ngân sách 80 ảnh, mô phỏng đã duyệt 80 ảnh; trong đó 67 ảnh có cảnh báo ngữ nghĩa, tổng cộng 76 cảnh báo ngữ nghĩa (một ảnh có thể có nhiều cảnh báo).

## 3. Calibration (2 ngưỡng)


| Tham số                | Khởi đầu | Đã chọn | Precision / Recall (trước → sau)                                                                 | Lý do (đánh đổi)                                                                                                                                                                     |
| ----------------------- | ----------- | ---------- | --------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `duplicates.phash_dist` | 2           | 16         | Near: 1.00/0.50 → 1.00/0.83; exact: 1.00/1.00 → 1.00/1.00                                         | Tăng recall bắt ảnh trùng gần mà precision trên calib vẫn giữ 1.00. Không chọn 20 vì precision của ảnh trùng byte giảm còn 0.33.                                         |
| `second_opinion.conf`   | 0.25        | 0.8        | Wrong class: 0.56/0.83 → 1.00/0.83; missing: 0.50/1.00 → 0.67/0.75; loose: 0.29/0.40 → 0.50/0.20 | Ngưỡng cao làm cảnh báo sai lớp đáng tin hơn, nhưng giảm recall cho missing/loose. False positive không đổi (0.31/1.00), vì ngưỡng này không điều khiển check đó. |

Calibration có thể đánh lừa vì chỉ có 39 ảnh và 6 ảnh trùng gần được chèn. Ở ngưỡng 16, recall trùng gần là 0.83 trên calib, nhưng khi chạy raw có 31/224 ảnh bị loại ở intake, so với 19/224 ở ngưỡng ban đầu 2. Vì vậy ngưỡng tốt trên calib có thể loại thêm ảnh thật; cần xem trực quan các cặp bị gắn cờ trước khi khẳng định chúng đều là ảnh trùng.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được

Khi chạy pipeline với --budget 0, kết quả là Rework: còn 6 lỗi bắt buộc. Mã thoát là 20 và pipeline không xuất dataset. Điều này chứng minh cổng chặn không cho dữ liệu lỗi đi tiếp khi chưa được người duyệt xử lý.

Hai điểm mù đã thấy: (1) ý kiến thứ hai không đáng tin tuyệt đối với box lỏng; ở calib, với `conf=0.8`, recall `POSSIBLE_LOOSE_BOX` chỉ 0.20 trên 5 lỗi chèn, tức chỉ bắt được 1/5. (2) máy không thể biết nhãn rỗng là ảnh nền thật hay bị thiếu nhãn; báo cáo v3 vẫn còn 5 cảnh báo `EMPTY_LABEL`, cần người mở ảnh để xác nhận.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)

Chưa chạy phần train Colab; đây là phần tùy chọn và hiện chưa có kết quả trong `submission/results/`.

## 6. Quyết định và ghi chú AI

Quyết định cuối: Release, vì không còn lỗi bắt buộc và cảnh báo còn lại là 13/193 ảnh (6,7%), thấp hơn ngưỡng 10%.

- Prompt chính: Nhờ AI giải thích yêu cầu trong docstring và hướng dẫn viết các module theo test tương ứng.
- Cách kiểm: Chạy test riêng cho từng module, toàn bộ 79 test, rồi chạy pipeline và kiểm tra báo cáo đầu ra.
- AI sai: Ban đầu AI hướng dẫn đặt xử lý `MISSING_LABEL_FILE` bên trong vòng lặp xử lý nhãn; test thất bại vì trường hợp này không có file nhãn. Đã chuyển xử lý ra ngoài vòng lặp và chạy lại test thành công.

*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
