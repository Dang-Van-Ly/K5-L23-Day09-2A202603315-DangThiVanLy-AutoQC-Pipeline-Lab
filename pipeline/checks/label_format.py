"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


def run(ds, cfg):
    issues = []
    for label_file in ds.label_files():
        stem = label_file.stem
        previous_boxes = []
        for line_no, text in ds.read_label_lines(stem) or []:
            try:
                box = parse_yolo_line(text)
                if not 0 <= box[0] < len(ds.classes):
                    issues.append(
                        Issue("label_format", ERROR, "BAD_CLASS_ID", stem, f"ID lớp {box[0]} không hợp lệ", line=line_no)
                    )
                    continue

                if box[3] <= 0 or box[4] <= 0:
                    issues.append(
                        Issue("label_format", ERROR, "BOX_ZERO", stem, "Chiều rộng hoặc chiều cao của box <= 0", line=line_no)
                    )
                    continue

                cx, cy, width, height = box[1:]
                left = cx - width / 2
                top = cy - height / 2
                right = cx + width / 2
                bottom = cy + height / 2
                overflow = max(0.0, -left, -top, right - 1.0, bottom - 1.0)
                tolerance = cfg["label_format"]["overflow_tol"]

                if overflow > tolerance:
                    issues.append(
                        Issue(
                            "label_format", ERROR, "BOX_OUT_OF_IMAGE", stem,
                            f"Box tràn khỏi ảnh {overflow:.4f}", line=line_no,
                            extra={"overflow": overflow},
                        )
                    )
                    continue

                if any(
                 previous[0] == box[0]
                 and iou_xywh(previous[1:], box[1:]) > cfg["label_format"]["dup_box_iou"]
                 for previous in previous_boxes
                ):
                 issues.append(
                     Issue("label_format", ERROR, "DUP_BOX", stem, "Box bị lặp", line=line_no)
                 )
                previous_boxes.append(box)
                
                size = ds.image_size(stem)
                if size is not None:
                    image_w, image_h = size
                    box_w_px = box[3] * image_w
                    box_h_px = box[4] * image_h
                    if min(box_w_px, box_h_px) < cfg["label_format"]["min_box_px"]:
                        issues.append(
                            Issue("label_format", WARN, "BOX_TINY", stem, "Box quá nhỏ", line=line_no)
                        )

                if box[3] * box[4] > cfg["label_format"]["max_box_frac"]:
                    issues.append(
                        Issue("label_format", WARN, "BOX_HUGE", stem, "Box chiếm phần quá lớn của ảnh", line=line_no)
                    )

            except ValueError as exc:
                issues.append(
                    Issue("label_format", ERROR, "BAD_FORMAT", stem, str(exc), line=line_no)
                )
    return issues
