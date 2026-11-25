# Dùng Doc2MD trên Windows

Hướng dẫn cho **Windows 10/11 64-bit**, khuyến nghị **Python 3.12**. Bộ chuyển đổi cơ bản cần Python 3.10+, phần OCR tùy chọn cần Python 3.11+. Không cần WSL cho cách cài native dưới đây.

## 1. Cài và lấy mã

1. Cài Python 3.12 từ [python.org](https://www.python.org/downloads/windows/). Bật Python launcher hoặc thêm Python vào PATH, rồi mở lại Terminal.
2. Tải ZIP từ [repo](https://github.com/nthunggs/doc2md) và giải nén, hoặc dùng Git:

```powershell
git clone https://github.com/nthunggs/doc2md.git
cd doc2md
.\setup-windows.cmd
```

Nếu tải ZIP, mở PowerShell/Terminal tại thư mục chứa `setup-windows.cmd`, rồi chạy lệnh cuối. Mạng chỉ cần cho bước cài thư viện. Bộ cài tạo `.venv` trong repo; không sửa Python hệ thống hoặc yêu cầu thay đổi execution policy. Không di chuyển riêng `.venv` sang máy/thư mục khác; chạy lại bộ cài ở vị trí mới.

## 2. Chuyển tài liệu

```powershell
.\doc2md.cmd "C:\Tai lieu\Tài liệu.docx" -o "C:\Tai lieu\Ket qua"
.\doc2md.cmd "C:\Tai lieu\Bảng tính.xlsx" -o "C:\Tai lieu\Ket qua"
.\doc2md.cmd "C:\Tai lieu\Văn bản.pdf" -o "C:\Tai lieu\Ket qua" --pdf-mode digital
.\doc2md.cmd "C:\Tai lieu\Bảng giá.pdf" -o "C:\Tai lieu\Ket qua" --pdf-layout auto
.\verify-doc2md.cmd "C:\Tai lieu\Ket qua\Bảng giá.md" --require-pages --require-table
```

Đặt đường dẫn trong dấu ngoặc kép, nhất là tên có dấu hoặc khoảng trắng. Các lệnh `.cmd` tự chọn Python trong `.venv`, không cần activate. Trong Command Prompt, bỏ tiền tố `.\` nếu đang ở cùng thư mục. Thêm `--overwrite` chỉ khi chủ động muốn thay Markdown cũ.

Pandoc là tùy chọn để chuyển DOCX đầy đủ hơn; cài theo [hướng dẫn chính thức](https://pandoc.org/installing.html#windows), mở lại Terminal và kiểm tra `pandoc --version`. Khi thiếu Pandoc, nhánh `python-docx` vẫn lấy tiêu đề và đoạn văn, nhưng bỏ bảng/ảnh. DOC/XLS cũ cần dùng WPS để lưu bản sao thành DOCX/XLSX.

## 3. Bật OCR cho PDF scan (tùy chọn)

Không cần các bước này nếu chỉ dùng DOCX/XLSX/PDF có chữ.

1. Cài **Tesseract 64-bit** theo [hướng dẫn Windows của OCRmyPDF](https://ocrmypdf.readthedocs.io/en/stable/installation.html#installing-on-windows). Có thể dùng Chocolatey trong Terminal quản trị nếu máy đã có Chocolatey:

```powershell
choco install tesseract --yes
```

2. Mở lại Terminal tại repo rồi chạy:

```powershell
.\setup-windows.cmd --ocr
.\doc2md.cmd "C:\Tai lieu\Bản scan.pdf" -o "C:\Tai lieu\Ket qua" --pdf-mode ocr
.\verify-doc2md.cmd "C:\Tai lieu\Ket qua\Bản scan.md" --require-pages
```

Tùy chọn `--ocr` cài OCRmyPDF và tải dữ liệu `eng`, `vie`, `osd` từ repo chính thức `tesseract-ocr/tessdata_fast` tại commit cố định vào `.venv/share/tessdata`. Bộ cài sao chép cấu hình `configs`/`tessconfigs` từ Tesseract đã cài để giữ chức năng xuất hOCR/PDF khi dùng dữ liệu ngôn ngữ riêng. Wrapper dùng dữ liệu này cho mỗi lần chuyển; không cần ghi thêm dữ liệu vào Program Files. Wrapper nhận Tesseract ở `C:\Program Files\Tesseract-OCR`; nếu cài vị trí khác, thêm thư mục chứa `tesseract.exe` vào PATH của Terminal.

Nhánh OCR mới dùng PyMuPDF đọc PDF sau OCR, nên không cần Poppler/`pdftotext`. Nó yêu cầu đầu ra PDF thường và tắt tối ưu ảnh; không dùng chuyển đổi PDF/A. Ghostscript không cần cho luồng này với phiên bản OCRmyPDF đã ghim. Apple Vision chỉ được dùng trên macOS.

OCR vẫn có thể sai dấu/số và không tự phục dựng bảng từ ảnh scan. Luôn đối chiếu tài liệu quan trọng với bản gốc.

## Lỗi thường gặp

| Hiện tượng | Cách xử lý |
| --- | --- |
| `Python not found` | Cài Python 3.12, mở lại Terminal; kiểm tra `py -3.12 --version`. |
| `Run setup-windows.cmd first` | Chạy bộ cài trong đúng thư mục đã giải nén/clone. |
| `.venv` dùng Python cũ | Đổi tên môi trường cũ, rồi chạy lại bộ cài bằng Python 3.12. |
| Thiếu OCRmyPDF/Tesseract/ngôn ngữ | Chạy `setup-windows.cmd --ocr`; kiểm tra vị trí Tesseract/PATH. |
| `Output already exists` | Đổi thư mục đích hoặc chủ động thêm `--overwrite`. |
| Lỗi mạng/proxy khi cài | Dùng cấu hình proxy/chứng chỉ đã được IT phê duyệt; không tắt xác minh TLS. |

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Để chạy thêm kiểm thử OCR thật sau khi cài đủ Tesseract và `--ocr`, mở PowerShell:

```powershell
$env:DOC2MD_TEST_OCR = "1"
$env:TESSDATA_PREFIX = "$PWD\.venv\share\tessdata"
$env:PATH = "$env:ProgramFiles\Tesseract-OCR;$env:PATH"
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Kết quả CI cho Windows, macOS và Linux: [GitHub Actions](https://github.com/nthunggs/doc2md/actions/workflows/tests.yml). Windows Python 3.12 chạy thêm OCR thật trên PDF scan được tạo tự động; bộ test không tải hồ sơ công ty.
