# Backlink Checker — công cụ kiểm tra backlink theo mô hình nhiều tầng

Tool kiểm tra: **link còn tồn tại không, có trỏ đúng đích không, và nếu hỏng thì
hỏng vì lý do gì**. Mọi thứ đặc thù cho từng dự án đều nằm trong file YAML ở
`config/`, không nằm trong code.

## Nguyên tắc số một

**Không hardcode thông tin site vào `src/`.** Money site, số tầng, tầng nào trỏ
về đâu, delay, danh sách domain cần render JS — tất cả nằm trong
`config/<site>.yaml`. Muốn thêm dự án mới thì copy `config/_mau.yaml`, không sửa
Python.

## Cấu trúc thư mục

```
backlink-checker/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── blcheck.bat / .ps1 / blcheck   launcher cho lệnh `blcheck`
├── config/
│   ├── _mau.yaml                  file mẫu có chú thích đầy đủ
│   └── checkbacklink.yaml         cấu hình dự án đang chạy
├── data/
│   └── backlinks_master.csv       stt, tier, sheet, source_url
├── src/
│   ├── cli.py         lệnh `blcheck` — chạy trọn gói, giao diện rich
│   ├── tui.py         banner, bảng màu, panel terminal
│   ├── bl_config.py   đọc + kiểm tra YAML, dò tier từ tên tab
│   ├── urlutil.py     chuẩn hoá URL dùng chung
│   ├── ingest.py      Google Sheets/Docs → master CSV đã lọc sạch
│   ├── checker.py     chạy check
│   ├── diagnose.py    biến tín hiệu thô thành mã lỗi + việc cần làm
│   ├── report.py      xuất XLSX tô màu
│   └── compare.py     so sánh 2 lần chạy
└── results/           kết quả, đặt tên theo ngày
```

## Chạy trọn gói bằng một lệnh

Sau khi cấu hình xong, chỉ cần một lệnh:

```powershell
.\blcheck.bat run
```

**Phải có `.\` ở đầu.** PowerShell không tìm lệnh trong thư mục hiện tại, gõ
`blcheck run` trần sẽ báo `The term 'blcheck' is not recognized`.

Lệnh này tự làm hết: nạp dữ liệu từ Google Sheet → làm sạch → check từng tier
**theo thứ tự `priority` trong config** (tier quan trọng nhất chạy trước) →
xuất CSV + XLSX tô màu → so sánh với lần chạy trước → in báo cáo.

Các cách gọi tương đương:

| Môi trường | Lệnh |
|-----------|------|
| PowerShell | `.\blcheck.bat run` hoặc `.\blcheck.ps1 run` |
| CMD | `blcheck run` |
| Git Bash | `./blcheck run` |
| Bất kỳ đâu | `python src/cli.py run` |

Muốn gõ `blcheck` trần từ mọi thư mục thì thêm `d:\toolcheck_backlink\backlink-checker`
vào biến môi trường PATH.

Gõ `.\blcheck.bat` không kèm lệnh sẽ vào chế độ tương tác (gõ `run`, `ingest`…
rồi Enter, thoát bằng `exit`).

### Các cờ hay dùng

| Cờ | Ý nghĩa |
|----|---------|
| `-c <file>` | File cấu hình khác, mặc định `config/checkbacklink.yaml` |
| `-t 1` | Chỉ chạy một tier |
| `-n 20` | Chỉ check 20 link đầu mỗi tier — **luôn dùng cái này lần chạy đầu** |
| `--skip-ingest` | Dùng master CSV có sẵn, không tải lại Google Sheet |
| `--js` / `--no-js` | Ép bật/tắt render JavaScript |
| `--no-diff` | Bỏ bước so sánh với lần trước |

### Lệnh con

| Lệnh | Việc |
|------|------|
| `.\blcheck.bat run` | Trọn gói |
| `.\blcheck.bat ingest --dry-run` | Chỉ nạp dữ liệu, xem trước không ghi file |
| `.\blcheck.bat check -t 2` | Chỉ check, không tải lại Sheet |
| `.\blcheck.bat diff <cũ> <mới>` | So sánh hai lần chạy |
| `.\blcheck.bat doisoat` | Đối soát với bên cung cấp: họ đưa bao nhiêu, ta nhận bao nhiêu, đòi bù bao nhiêu |

### Lần chạy đầu nên làm gì

```powershell
.\blcheck.bat ingest --dry-run   # xem tab nào vào tier nào, có tab nào lạc không
.\blcheck.bat run -n 20          # thử 20 link mỗi tier, xác nhận mạng chạy được
.\blcheck.bat run                # chạy thật
```

### Cách tool đọc trang: hai lượt

Lượt 1 tải HTML thô bằng httpx cho **toàn bộ** danh sách — nhanh. Lượt 2 chỉ mở
Chromium cho những link mà lượt 1 chưa đọc được nội dung thật:

- không tìm thấy thẻ `<a>` về đích
- HTTP 401/403/405/406/429/500/502/503 — máy chủ từ chối *cách đọc*, không phải
  trang đã chết
- domain nằm trong `js.force_domains`

Đo trên dự án hiện tại: cách này giảm số lần mở trình duyệt từ 1.764 xuống
khoảng 600–700, đồng thời tier 1 và 2 mới thật sự được render (trước đây
`auto_tiers: [3, 4]` bỏ sót đúng hai tầng quan trọng nhất).

Tắt bằng `js.escalate: false` để quay về cách cũ.

`js.wait_until` phải là `domcontentloaded`, **không** phải `networkidle` —
trang có polling (mn.co, penzu) không bao giờ "idle" nên networkidle luôn
timeout và làm hỏng cả bước render. Chờ thêm bằng `js.wait_after`.

### Bắt buộc cài Playwright trước khi tin kết quả tier 3/4

```powershell
pip install playwright
playwright install chromium
```

Thiếu Playwright, các link cần render JavaScript sẽ mang mã
`CHUA_CAI_PLAYWRIGHT` — tool **không** kết luận mất link, nhưng cũng chưa đọc
được nội dung thật. `blcheck run` in cảnh báo ngay đầu nếu thiếu.

Tier 4 rất lâu (hơn 1.000 link + render trình duyệt) nên để chạy nền hoặc qua
đêm. Muốn tách ra thì `blcheck run -t 4` riêng.

---

## Flow chạy thủ công từng bước

Phần dưới đây là cách gọi trực tiếp từng script — dùng khi cần debug hoặc chỉ
muốn chạy đúng một khâu.

### Bước 0 — Nạp dữ liệu từ Google Sheets

Sheet phải được share ở chế độ **Anyone with the link → Viewer**, nếu không
Google trả 403 và script sẽ báo đúng lỗi đó.

```bash
python src/ingest.py -c config/checkbacklink.yaml \
  --url "https://docs.google.com/spreadsheets/d/XXXX/edit" --dry-run
```

`--dry-run` in ra: mỗi tab được gán vào tier nào, bao nhiêu link, loại bỏ bao
nhiêu link trùng/hỏng. **Luôn chạy `--dry-run` trước.** Nếu có tab bị báo
"không khớp tier nào", thêm từ khoá vào `tiers.<N>.match` rồi chạy lại. Khi số
liệu đã đúng thì bỏ `--dry-run` để ghi ra master CSV.

Ingest tự động làm những việc sau:
- gỡ ký tự rác, khoảng trắng, zero-width do copy từ Excel/Docs
- thêm `https://` cho URL viết thiếu scheme
- bỏ tham số tracking (`utm_*`, `fbclid`, `gclid`…)
- **khử trùng lặp toàn cục** theo dạng chuẩn hoá (bỏ www, bỏ slash cuối)
- loại URL trỏ về chính money site (không phải backlink)
- loại tab nằm trong `ingest.drop_sheets`
- gán tier theo `match`, ưu tiên từ khoá dài hơn (nên `Submiss Web 2.0 tầng 3`
  vào tier 3 chứ không rơi vào tier 2 chỉ vì chứa chuỗi `web 2.0`)

#### Tab có nhiều cột URL

Mặc định ingest quét **mọi ô** trong tab. Đúng với tab như
`Social Bookmarks DA cao tầng 3` — nó có 2 cột URL và cả hai đều là backlink thật.

Nhưng tab `Link Page rank cao` có cột `Tên Miền` (trang chủ) và cột `Link Đặt`
(backlink thật). Quét hết sẽ nhân đôi số link và thêm 50 URL trang chủ vô nghĩa.
Khai báo cột cần lấy:

```yaml
ingest:
  sheet_columns:
    "link page rank cao": ["link dat"]
```

Ingest tìm dòng tiêu đề trong 10 dòng đầu của tab, lấy đúng cột đó. Không tìm
thấy tiêu đề khớp thì in cảnh báo và quay lại quét toàn bộ ô.

Dấu hiệu nhận biết đang lấy nhầm cột: cuối phần chạy có cảnh báo
**"URL chỉ có tên miền, không có đường dẫn"**. Không phải lúc nào cũng sai —
9 URL `*.mystrikingly.com/` trong dự án này là trang chủ site vệ tinh thật, đặt
link ngay ở trang chủ. Nhưng `https://www.tripadvisor.com` thì chắc chắn là
nhầm cột.

### Bước 1 — Test nhanh 20 link

```bash
python src/checker.py -c config/checkbacklink.yaml --tier 1 --limit 20 -o results/test
```

Xác nhận mạng chạy được. Nếu cả 20 dòng đều `TIMEOUT` hoặc
`DOMAIN_KHONG_PHAN_GIAI` thì vấn đề nằm ở mạng/proxy, dừng lại xử lý trước.

### Bước 2 — Chạy từng tier, theo thứ tự ưu tiên

```bash
python src/checker.py -c config/checkbacklink.yaml --tier 2   # nhỏ, quan trọng nhất
python src/checker.py -c config/checkbacklink.yaml --tier 1
python src/checker.py -c config/checkbacklink.yaml --tier 3   # tự bật JS theo config
python src/checker.py -c config/checkbacklink.yaml --tier 4   # chạy nền / qua đêm
```

Tên file kết quả tự sinh theo `output.filename`, mặc định
`results/2026-08-25_huthamcautienphat_tier1.csv` và `.xlsx`.

Cờ `--js` chỉ cần khi muốn ép render cho một tier không bật sẵn. Ngược lại
`--no-js` để tắt tạm. Các domain trong `js.force_domains` luôn được render lại
kể cả khi không có `--js` — đây là chỗ khai báo những site kiểu
`.thezenweb.com`, `.ampblogs.com`, `mediajx.com` vốn sinh nội dung bằng
JavaScript và sẽ cho hàng loạt `NOT_FOUND` giả nếu đọc HTML thô.

### Bước 3 — So sánh với lần chạy trước

```bash
python src/compare.py results/2026-08-11_huthamcautienphat_tier1.csv \
                      results/2026-08-25_huthamcautienphat_tier1.csv \
                      -o results/thay-doi.csv
```

In ra link vừa mất, vừa khôi phục, và link tuy vẫn `FOUND` nhưng đổi kiểu lỗi.

### Bước 4 — Lặp lại 2 tuần/lần

Giữ nguyên quy ước tên file để bước 3 hoạt động.

## Đối soát với bên cung cấp link

Câu hỏi khác hẳn với "link nào hỏng": **họ nói giao N link, thực tế ta nhận
được bao nhiêu, và họ phải bù lại bao nhiêu.**

```powershell
python src/cli.py doisoat -c config/checkbacklink.yaml
```

Lệnh này nạp lại nguồn gốc (Google Sheet) để **đếm số thô trước khi lọc** — số
này không có trong `backlinks_master.csv` vì file đó đã sạch rồi. Sau đó ghép
với kết quả check mới nhất trong `results/`.

Ra một bảng theo từng tab nguồn:

```
Tab nguồn          Họ đưa   Trùng  Money   Nhận   Chết   Đòi bù
Tang 4_Bookmarks      421     418      0      3      0      418
```

Và file `results/<ngày>_<site>_doi-soat.xlsx` gồm 3 sheet:
- **Đối soát** — bảng trên + khối "ĐỀ NGHỊ BÙ LẠI" đã cộng sẵn.
- **Link trùng** — từng URL bị lặp: số lần xuất hiện, tab đặt lần đầu, tab lặp lại,
  trùng chéo tab hay trùng trong cùng một tab.
- **Link chết - gửi họ** — từng URL chết kèm mã lỗi và chẩn đoán, làm bằng chứng.

### Bảng trùng lặp giữa các tab

Console in thêm bảng cặp tab. Đây là con số mang đi nói chuyện được, mạnh hơn
nhiều so với một danh sách vài trăm URL lẻ tẻ:

```
Tab đặt lần đầu        Tab lặp lại          Số URL
Tang 4_Blog Comment    Tang 4_Bookmarks        418
web 2.0                Link bài viết trên Blog  10
```

Đọc dòng đầu: tab `Tang 4_Bookmarks` thực chất là **bản sao** của
`Tang 4_Blog Comment`, không phải nguồn mới.

Chú ý cách đếm: link đặt **lần đầu** được giữ lại và tính là đã giao. Chỉ các
lượt lặp về sau mới vào cột `Thừa` và được tính vào đề nghị bù. Nên tab bị coi
là "lặp lại" phụ thuộc vào thứ tự tab trong Google Sheet.

### Bốn khoản được tính là chưa giao đủ

Định nghĩa nằm ở `KHOAN_BU` trong [doisoat.py](src/doisoat.py):

| Khoản | Vì sao không tính là đã giao |
|-------|------------------------------|
| Link giao trùng | Cùng một URL đếm hai lần, chỉ tính được một |
| Trỏ về money site | Đó là link của chính mình, không phải backlink |
| URL hỏng | Ô dữ liệu không phải URL mở được |
| Chết khi kiểm tra | 404 / 410 / domain hết hạn / bài bị gỡ |
| Trang noindex | Thẻ `<a>` còn, nhưng Google không index trang chứa nó nên link không truyền được giá trị nào |

Lưu ý cách đọc khoản **"Trang noindex"**: trong file kết quả check nó nằm ở nhóm
`Link còn` — tool nhìn thấy thẻ `<a>`, không cần ai mở tay xác minh. Nhưng trong
đối soát thì nó **không tính là đã giao**, vì trang không được index thì link
không truyền được giá trị nào. Hai câu hỏi khác nhau, hai câu trả lời khác nhau
trên cùng một dòng dữ liệu.

Nhóm **"phải check tay"** cố ý **không** đưa vào yêu cầu bù: tool chưa đọc được
nội dung thật nên chưa có bằng chứng. Đòi bù bằng số liệu chưa xác minh là tự
làm yếu lập luận của mình. Con số này hiện riêng ở khối "Chưa tính vào yêu cầu bù".

Chưa chạy check bao giờ thì cột `Chết` bằng 0 và tool cảnh báo rõ — đó là vì
chưa đo, không phải vì không có link chết.

## Đọc file kết quả

File `.xlsx` có 4 sheet:
- **Chi tiết** — mỗi link một dòng, tô màu cả dòng theo mức độ, link hỏng nặng
  nhất nằm trên cùng. Đã bật freeze dòng tiêu đề và auto-filter.
- **Tổng hợp** — mở đầu bằng khối **CHỐT LẠI**, rồi mới đến bảng theo tier và
  theo mã lỗi.
- **Cần check tay** — danh sách từng link tool chưa kết luận được, kèm lý do và
  cách kiểm tra. Sheet này đọc xong là biết phải mở URL nào.
- **Chú giải** — ý nghĩa của kết luận và của từng màu mức độ.

File `.csv` chứa đúng dữ liệu đó, dùng cho `compare.py` và cho git.

### Hai tầng phân loại — đừng lẫn

Mỗi link mang **hai** nhãn độc lập, trả lời hai câu hỏi khác nhau:

| Cột | Trả lời câu hỏi |
|-----|-----------------|
| `ket_luan` | Kết quả này có đáng tin không, có phải mở tay kiểm tra không? |
| `muc_do` | Nếu phải xử lý thì gấp đến đâu? |

### Tầng kết luận

| Kết luận | Màu | Nghĩa | Phải làm gì |
|----------|-----|-------|-------------|
| Link còn | xanh lá | Tool đọc được trang và **nhìn thấy thẻ `<a>`** | Không cần mở tay. Xem `muc_do` để biết link tốt hay còn khiếm khuyết. Nhóm này gồm cả `TRANG_NOINDEX` và `TRO_SAI_TANG` — link vẫn nằm đó, chỉ là giá trị thấp hoặc trỏ sai tầng |
| Link mất | đỏ | Tool đọc được trang và chắc chắn link không còn (404/410/domain hết hạn/bài bị gỡ) | Không cần mở tay. Thay nguồn mới |
| Phải check tay | vàng | Tool **không đọc được** nội dung thật (chặn bot, captcha, tường đăng nhập, chưa render JS, timeout…) | **Chưa phải là link mất.** Xem sheet "Cần check tay" |

Nhóm "Phải check tay" được chia tiếp theo cột `cach_xu_ly`:

- **Chạy lại tool** — máy làm. Cài Playwright, bật `--js`, giãn delay rồi chạy
  lại là xong cả cụm. Làm nhóm này trước, thường nó rụng gần hết.
- **Mở trình duyệt** — người làm. Mở URL, `Ctrl+F` tìm tên miền money site.

Bảng ánh xạ mã lỗi sang kết luận nằm ở `VERDICT` trong [diagnose.py](src/diagnose.py).
Thêm mã lỗi mới vào `CATALOG` thì **phải** thêm vào `VERDICT` cùng lúc — mã lạ
mặc định rơi vào "Phải check tay".

### Bảng màu theo mức độ

| Mức độ | Màu | Nghĩa |
|--------|-----|-------|
| CHẾT | đỏ nhạt | Link mất hẳn, phải thay nguồn mới |
| NẶNG | cam | Link còn nhưng đang hỏng, xử lý sớm |
| CẢNH BÁO | vàng | Link còn, giá trị thấp hơn kỳ vọng hoặc chưa kết luận được |
| GHI CHÚ | xanh nhạt | Không sai, chỉ để biết |
| TỐT | xanh lá | Không cần làm gì |

Mức độ được điều chỉnh theo `priority` của tier: tier `priority: 1` bị **nâng
một bậc** (lỗi ở tầng xương sống thì nghiêm trọng hơn), tier `priority >= 4`
được **hạ một bậc** (chỉ theo dõi tổng quan).

### Các cột cần chú ý

- `ket_luan` — cột lọc quan trọng nhất. Lọc "Phải check tay" ra là có ngay danh
  sách việc còn tồn.
- `diag_code` — mã lỗi ngắn, dùng để lọc trong Excel.
- `chan_doan` — giải thích tiếng Việt.
- `viec_can_lam` — hành động cụ thể.
- `canh_bao_them` — vấn đề phụ. Một link vừa `nofollow` vừa trỏ sai URL thì
  `diag_code` chỉ lấy cái nặng nhất, phần còn lại nằm ở cột này.
- `khop_tang` — link này thực sự rơi vào tầng nào: `money`, `tier 2`, `tier 3`…
  So với đích đầu tiên khai trong `targets` của tier để biết cấu trúc thật có
  khớp sơ đồ không.
- `rendered` — `http` hay `playwright`. Kết luận "mất link" từ dòng `http` trên
  một domain render JS là không đáng tin.

## Bảng mã lỗi

Nguồn thật nằm ở `CATALOG` trong [diagnose.py](src/diagnose.py) — thêm case mới
thì thêm vào đó.

### Trang chết hẳn

| Mã | Tín hiệu | Xử lý |
|----|----------|-------|
| `DOMAIN_KHONG_PHAN_GIAI` | DNS thất bại | Domain hết hạn. Bỏ khỏi danh sách |
| `KET_NOI_TU_CHOI` | Connection refused/reset | Kiểm tra tay một lần rồi thay nguồn |
| `HTTP_404` | 404 | Bài bị xoá. Đăng lại hoặc thay nguồn |
| `HTTP_410` | 410 Gone | Xoá vĩnh viễn, không đăng lại URL cũ được |
| `SOFT_404` | 200 nhưng title là trang lỗi | Coi như mất link |
| `DOMAIN_RAO_BAN` | nội dung là trang parking/rao bán | Bỏ. Có thể độc hại |
| `CHUYEN_VE_TRANG_CHU` | bài viết bị redirect về trang chủ | Dấu hiệu bài bị gỡ |

### Chưa kết luận được — đừng vội báo mất link

| Mã | Tín hiệu | Xử lý |
|----|----------|-------|
| `HTTP_403_CHAN_BOT` | 403 | Thường là Cloudflare chặn bot. Bật `--js` hoặc mở tay |
| `BI_CHAN_CAPTCHA` | nội dung có captcha / "Just a moment" | Kiểm tra tay |
| `HTTP_429` | 429 | Ta bắn quá nhanh. Tăng `per_domain_delay` rồi chạy lại |
| `TIMEOUT` | hết thời gian chờ | Chạy lại riêng link đó với timeout cao hơn |
| `HTTP_5XX` | 500–599 | Lỗi tạm. Chạy lại sau vài giờ |
| `CAN_BAT_JS` | domain trong `force_domains` mà chưa render | Chạy lại với `--js` |
| `CHUA_CAI_PLAYWRIGHT` | tier cần JS nhưng máy chưa cài Playwright | Cài rồi chạy lại tier đó |
| `CHUA_RENDER_DUOC` | đã mở bằng Chromium nhưng vẫn không tải được nội dung | Mở tay bằng trình duyệt |
| `TUONG_DANG_NHAP` | nội dung đòi đăng nhập | Kiểm tra bằng tài khoản đã đăng bài |
| `SSL_LOI` | chứng chỉ hỏng | Trang có thể vẫn sống, xác nhận tay |

### Link mất giá trị dù vẫn tồn tại

| Mã | Tín hiệu | Xử lý |
|----|----------|-------|
| `LINK_BI_GO` | trang sống, đọc được nội dung thật, không còn thẻ `<a>` nào về hệ thống mình | Admin gỡ link. Đăng lại |
| `TRO_SAI_TANG` | link còn, trỏ đúng hệ thống mình nhưng **sai tầng** so với khai báo | Không phải link hỏng. Sửa khai báo `targets` cho khớp thực tế, hoặc đặt lại link |
| `TRANG_NOINDEX` | meta robots noindex, thẻ `<a>` vẫn còn | Google không tính. Link **chưa mất** (không phải mở tay xác minh) nhưng **có tính vào khoản đòi bù** — mua backlink là mua giá trị truyền về, không phải mua một thẻ `<a>` nằm trên trang Google không đọc tới |
| `CANONICAL_KHAC` | canonical trỏ đi nơi khác | Giá trị chuyển sang URL khác |
| `NOFOLLOW` | rel nofollow/ugc/sponsored | Không truyền sức mạnh |
| `SAI_URL_DICH` | đúng domain, sai trang | Sửa về đúng URL nếu còn quyền |
| `LINK_QUA_TRUNG_GIAN` | href đi qua rút gọn/redirect | Ưu tiên link trỏ thẳng |
| `TRANG_NHIEU_LINK_RA` | vượt `thresholds.outbound_link_limit` | Đặc trưng link farm |
| `ANCHOR_RONG` / `ANCHOR_LA_URL` | anchor rỗng hoặc là URL trần | Không gấp |

## Thứ tự ưu tiên xử lý

1. Tier có `priority: 1`, mức `CHẾT` — kéo sập cả nhánh phía dưới.
2. Tier trỏ thẳng money site, mức `CHẾT`.
3. Mức `NẶNG` ở các tier trỏ thẳng money site.
4. Mức `CẢNH BÁO` — xử lý sau, nhiều trường hợp chỉ cần xác nhận tay.
5. Tier `priority >= 4` — chỉ theo dõi tổng quan, không xử lý từng link.

## Chỉnh tham số

Sửa trong file YAML, không sửa Python:

```yaml
network:
  concurrency: 8         # tăng 15–20 nếu mạng khoẻ, dễ bị chặn IP hơn
  per_domain_delay: 1.5  # KHÔNG hạ dưới 1.0
  timeout: 25
  retries: 1
```

Nếu đặt `per_domain_delay` dưới 1.0, tool in cảnh báo ngay khi khởi động.

## Việc KHÔNG nên làm

- Không chạy toàn bộ danh sách trong một lệnh ở lần đầu. Test `--limit 20` trước.
- Không hạ `per_domain_delay` xuống dưới 1 giây — nhiều link tầng dưới nằm chung
  một vài domain directory, bắn nhanh sẽ bị ban IP và cho ra `HTTP_429` giả.
- Không kết luận SEO dựa trên tổng số `FOUND`. Con số đó bị thổi phồng bởi khối
  link profile/bookmark/comment tự động.
- Không sửa `data/*.csv` bằng Excel rồi lưu lại — Excel làm hỏng encoding UTF-8
  của URL tiếng Việt có dấu. Sửa bằng VS Code, hoặc chạy lại `ingest.py`.
- Không coi `NOT_FOUND` trên domain render JS là mất link nếu cột `rendered` ghi
  `http`.

## Việc tool này KHÔNG làm được

Tool trả lời "link có tồn tại và trỏ đúng không". Nó **không** biết Google đã
index trang chứa link hay chưa — cần Google Search Console API hoặc dịch vụ như
Ahrefs / Majestic. Link tồn tại nhưng trang không được index thì gần như không
truyền giá trị. Cột `indexable` chỉ đọc được thẻ `noindex` và `canonical` trên
trang, không phải trạng thái index thật.

Tool cũng không đo DR/DA/traffic của domain nguồn.

---

# Bối cảnh dự án hiện tại — huthamcautienphat.com

Cấu hình: [config/checkbacklink.yaml](config/checkbacklink.yaml)

Money site `huthamcautienphat.com`, trang mục tiêu chính
`/dich-vu-hut-ham-cau`. Dữ liệu gốc là file Excel 12 sheet, đã gộp và làm sạch
thành `data/backlinks_master.csv` với 2.691 link duy nhất.

| Tier | Số link | Trỏ về | priority |
|------|---------|--------|----------|
| 1 | 897 | money site | 2 |
| 2 | 30 | money site | 1 |
| 3 | 719 | tập URL tier 2 | 4 |
| 4 | 1.045 | tập URL tier 3 | 4 |

Vì không có dữ liệu ghi rõ mỗi link tier 3/4 phải trỏ vào URL cụ thể nào, tool
kiểm tra theo tập hợp: "link này có trỏ vào **bất kỳ** URL nào thuộc tầng trên
không". Tập đích được dựng từ chính master CSV.

### Ghi chú chất lượng dữ liệu

- Sheet `web 2.0` (10 URL) là tập con của `Link bài viết trên Blog` (30 URL).
  Thực chất chỉ có 30 vệ tinh tier 2: penzu, pearltrees, Google Sites, Evernote,
  notebook.ai, ofuse, jimdosite, blogspot, notion, wakelet.
- Tier 2 được đặt `priority: 1` vì 1.764 link tier 3 và 4 đều đổ vào đúng 30 URL
  này. Mất một URL tier 2 là mất cả một nhánh lớn.
- Tier 1 tuy đặt tên "DR cao" nhưng phần lớn là link profile trên job board và
  site Wix nước ngoài (username chung `tienphathc`). Chỉ ~12 link đầu là bài đăng
  thật trên diễn đàn Việt Nam.
- Sheet `Sheet1` trong file Excel gốc là dữ liệu rác của dự án khác, đã đưa vào
  `ingest.drop_sheets`.
- Khoảng 90% khối lượng link là profile/bookmark/comment tự động — loại link
  Google gần như bỏ qua. Chỉ nên hành động dựa trên tier 1 và tier 2.
