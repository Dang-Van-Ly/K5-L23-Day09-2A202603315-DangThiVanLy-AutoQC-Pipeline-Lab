"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


def fix(ds, issues, cfg):
    fixes = []
    drop_codes = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
    lines_to_drop = defaultdict(set)
    lines_to_clip = defaultdict(dict)
    images_to_remove = {}

    for issue in issues:
        if issue.severity != ERROR:
            continue
        if issue.code.startswith("DUP_IMAGE_") or issue.code in {
            "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"
        }:
            images_to_remove[issue.image] = issue
            continue
        if issue.code in drop_codes and issue.line is not None:
            lines_to_drop[issue.image].add(issue.line)
        elif issue.code == "BOX_OUT_OF_IMAGE" and issue.line is not None:
            lines_to_clip[issue.image][issue.line] = issue

    stems = (set(lines_to_drop) | set(lines_to_clip)) - set(images_to_remove)
    for stem in stems:
        path = ds.label_path(stem)
        if not path.exists():
            continue

        original_lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        updated_lines = []

        for line_no, original in enumerate(original_lines, start=1):
            before = original.rstrip("\r\n")

            if line_no in lines_to_drop[stem]:
                fixes.append({
                    "image": stem, "line": line_no, "action": "drop_line",
                    "before": before, "after": "",
                })
                continue

            if line_no in lines_to_clip[stem]:
                cls, cx, cy, width, height = parse_yolo_line(before)
                x1 = max(0.0, cx - width / 2)
                y1 = max(0.0, cy - height / 2)
                x2 = min(1.0, cx + width / 2)
                y2 = min(1.0, cy + height / 2)

                if x2 <= x1 or y2 <= y1:
                    fixes.append({
                        "image": stem, "line": line_no, "action": "drop_line",
                        "before": before, "after": "",
                    })
                    continue

                clipped = (
                    f"{cls} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} "
                    f"{x2 - x1:.6f} {y2 - y1:.6f}"
                )
                ending = "\r\n" if original.endswith("\r\n") else "\n" if original.endswith("\n") else ""
                updated_lines.append(clipped + ending)
                fixes.append({
                    "image": stem, "line": line_no, "action": "clip_box",
                    "before": before, "after": clipped,
                })
                continue

            updated_lines.append(original)

        path.write_text("".join(updated_lines), encoding="utf-8")

    for stem, issue in images_to_remove.items():
        image_path = ds.image_path(stem)
        if image_path is None:
            continue

        label_path = ds.label_path(stem)
        image_path.unlink()
        if label_path.exists():
            label_path.unlink()

        fixes.append({
            "image": stem,
            "line": "",
            "action": "remove_image",
            "before": image_path.name,
            "after": "",
        })

    for issue in issues:
        if issue.severity != ERROR:
            continue

        if issue.code == "MISSING_LABEL_FILE" and issue.image not in images_to_remove:
            fixes.append({
                "image": issue.image,
                "line": "",
                "action": "needs_label",
                "before": "(không có file)",
                "after": "chuyển người gán",
            })
        elif issue.code == "BAD_CLASS_NAME":
            path = ds.yaml_path
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            before = data.get("names")
            data["names"] = cfg["classes"]
            path.write_text(
                yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            fixes.append({
                "image": "data.yaml",
                "line": "",
                "action": "rename_classes",
                "before": str(before),
                "after": str(cfg["classes"]),
            })
    return fixes