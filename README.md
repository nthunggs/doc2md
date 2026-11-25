# Doc2MD

Công cụ của team để chuyển **DOCX, XLSX, PDF digital và PDF scan** sang Markdown trên máy cục bộ. Repo riêng tư này chứa mã công cụ và dữ liệu kiểm thử được tạo tự động; không chứa hồ sơ nghiệp vụ.

## Cài đặt

Cần Python **3.10 trở lên**:

```bash
git clone https://github.com/nthunggs/doc2md.git
cd doc2md
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Các phiên bản trong `requirements.txt` là bộ dependency đã kiểm thử cho lần đưa mã lên repo này.

- **DOCX:** khuyến nghị cài Pandoc để xử lý bảng, ảnh và định dạng tốt hơn. Nếu không có, chương trình dùng `python-docx` để lấy đoạn văn và tiêu đề; nhánh dự phòng này không chuyển bảng/ảnh.
- **PDF scan trên macOS:** dùng Apple Vision khi có trình biên dịch `swiftc` (Xcode Command Line Tools). Helper Swift nằm trong `tools/vision_ocr.swift` và được biên dịch khi cần.
- **PDF scan trên hệ điều hành khác:** cần OCRmyPDF, Poppler (`pdftotext`) và dữ liệu Tesseract `vie`/`eng` đã cài. Khi cả OCRmyPDF và `pdftotext` có sẵn, chương trình ưu tiên backend này, kể cả trên macOS.
- DOC/XLS cũ chưa được CLI nhận trực tiếp. Dùng WPS Office để lưu **bản sao** thành DOCX/XLSX trước; giữ nguyên file gốc.

Việc cài dependency có thể cần mạng. Pipeline chuyển đổi không gọi API AI bên ngoài để gửi tài liệu đi.

## Chuyển tài liệu

```bash
python tools/fast_doc2md.py "/duong-dan/tai-lieu.docx" -o "./output"
python tools/fast_doc2md.py "/duong-dan/bang.xlsx" -o "./output"
python tools/fast_doc2md.py "/duong-dan/tai-lieu.pdf" -o "./output"
```

Nếu không truyền `-o`, Markdown được đặt cạnh file nguồn. Chương trình giữ nguyên nguồn và từ chối ghi đè Markdown đã tồn tại; chỉ thêm `--overwrite` khi chủ động muốn thay kết quả cũ.

### Chế độ PDF

```bash
# PDF đã có lớp chữ, lấy văn bản nhanh
python tools/fast_doc2md.py "tai-lieu.pdf" -o output --pdf-mode digital

# Phục dựng bảng và biểu mẫu khi nhận diện được
python tools/fast_doc2md.py "bang-gia.pdf" -o output --pdf-layout auto

# PDF scan, buộc dùng OCR
python tools/fast_doc2md.py "ban-scan.pdf" -o output --pdf-mode ocr
```

- `--pdf-mode auto` (mặc định): lấy mẫu tối đa 5 trang để chọn digital/OCR.
- `--pdf-layout fast` (mặc định): lấy text, không phục dựng bảng.
- `--pdf-layout auto`: dò bảng có đường viền hoặc bảng văn bản theo từng trang.
- `--pdf-layout tables`: luôn thử dò bảng; chậm hơn `fast`. Layout này áp dụng cho nhánh PDF digital, không phục dựng bảng từ ảnh scan.

## Kiểm tra kết quả

```bash
python tools/verify_doc2md.py "output/tai-lieu.md" --min-words 50
python tools/verify_doc2md.py "output/bang-gia.md" --require-pages --require-table
```

Verifier trả JSON và mã thoát khác 0 khi thiếu số từ yêu cầu, có lỗi OCR, thiếu mốc trang/bảng theo yêu cầu, hoặc độ rộng hàng trong bảng không nhất quán. Các cảnh báo vẫn cần người đọc xem lại.

**Giới hạn cần biết:**

- Mốc `<!-- Page N -->` được tạo trong nhánh PDF digital và Apple Vision. Nhánh OCRmyPDF hiện xuất text qua `pdftotext`, chưa chèn mốc trang dạng này; không dùng `--require-pages` cho nhánh đó.
- OCR có thể sai dấu, số hoặc ký tự. Bảng scan, biểu mẫu phức tạp và văn bản nhiều cột cần đối chiếu với nguồn.
- XLSX đọc giá trị đã cache (`data_only=True`), không tính lại công thức. Công thức chưa có giá trị cache có thể cho ô trống.
- Verifier kiểm tra cấu trúc và một số dấu hiệu lỗi, không chứng minh nội dung chuyển đổi đầy đủ hoặc chính xác tuyệt đối.
- Không tự động sao chép kết quả vào Obsidian hay thư viện hồ sơ.

## Kiểm thử

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

Bộ 5 test hiện có kiểm tra lấy mẫu trang, PDF bảng không đường viền, nhánh PDF nhanh, XLSX không sinh header giả và mức tăng bộ nhớ Python khi xử lý PDF dài. Fixture được sinh trong thư mục tạm và tự dọn sau mỗi test. Bộ này chưa kiểm thử tích hợp OCR/Pandoc.

`tools/benchmark_doc2md.py` là tiện ích so sánh với một bản converter cũ do người chạy cung cấp qua `--doc2md`; xem `--help` để dùng. Không kèm hồ sơ hay kết quả benchmark nội bộ.

## Dùng với trợ lý AI

`SKILL.md` mô tả cách gọi công cụ và kiểm tra kết quả. `agents/openai.yaml` cung cấp thông tin hiển thị cho môi trường hỗ trợ skill. Khi cài hoặc sao chép skill, cần giữ cùng bố cục `tools/` bên cạnh `SKILL.md`.
