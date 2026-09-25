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
│   ├── robotscheck.py đọc robots.txt, hỏi "Googlebot có được vào không"
│   ├── diagnose.py    biến tín hiệu thô thành mã lỗi + việc cần làm
│   ├── report.py      xuất XLSX tô màu
│   ├── ghichu.py      dựng lại file nguồn gốc, thêm cột chú thích tô màu
│   ├── nhanh.py       nối các tầng: link sống nhưng URL tầng trên đã chết
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
xuất CSV + XLSX tô màu → so sánh với lần chạy trước → in báo cáo → dựng lại
**file gốc có chú thích** → xuất **file đối soát** với bên cung cấp.

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
| `--no-ghichu` | Bỏ bước xuất file gốc có chú thích (bước 5) |
| `--no-doisoat` | Bỏ bước xuất file đối soát (bước 6) |

Lệnh `check` bỏ qua cả bước 5 lẫn bước 6, vì hai bước đó phải tải lại Google Sheet.

### Lệnh con

| Lệnh | Việc |
|------|------|
| `.\blcheck.bat run` | Trọn gói |
| `.\blcheck.bat ingest --dry-run` | Chỉ nạp dữ liệu, xem trước không ghi file |
| `.\blcheck.bat check -t 2` | Chỉ check, không tải lại Sheet |
| `.\blcheck.bat diff <cũ> <mới>` | So sánh hai lần chạy |
| `.\blcheck.bat doisoat` | Đối soát với bên cung cấp: họ đưa bao nhiêu, ta nhận bao nhiêu, đòi bù bao nhiêu |
| `.\blcheck.bat ghichu` | Xuất lại **file nguồn gốc** giữ nguyên từng tab, thêm cột chú thích tô màu |

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

**Trang đã trả mã 404/410 thì không mở Chromium.** Trước đây nhánh dự phòng
"lỗi kết nối" bắt nhầm cả trang có mã HTTP. Đo trên lần chạy 2026-09-06: 29 dòng
HTTP 404, **không dòng nào** giữ được mã `HTTP_404` — Chromium đọc trang báo lỗi
rồi kết luận "không thấy link", 13 dòng rơi vào `TRANG_RONG` (phải check tay).
Giờ nhánh đó chỉ áp cho lỗi không có mã HTTP, và nếu Chromium nhận 404/410 thì
cũng giữ nguyên mã.

### Googlebot là chuẩn

Tool trả lời "link có truyền giá trị SEO không", mà Google chỉ truyền giá trị
qua những gì **Googlebot nhìn thấy**. Nên ngoài lượt đọc bằng User-Agent Chrome
(góc nhìn người xem), mỗi URL còn được tải lại với User-Agent Googlebot điện
thoại (Google index theo bản điện thoại), và **kết luận cuối cùng đi theo
Googlebot**. Luật nằm ở `phan_xu()` trong [diagnose.py](src/diagnose.py):

| Người xem thấy | Google thấy | Kết luận |
|---|---|---|
| thấy link | thấy link | theo trang Googlebot nhận (OK / nofollow / noindex…) |
| thấy link | bị báo 404 | `GOOGLE_BI_BAO_404` — Link mất |
| thấy link | không thấy link / bị chuyển đi | `AN_LINK_VOI_GOOGLE` — Link mất |
| bị chuyển đi / 404 / link bị gỡ | thấy link | `CLOAKING_NGUOI_DUNG` — **Link còn**, chỉ ghi chú |
| bị chặn captcha / 403 | thấy link | theo trang Googlebot nhận — Link còn, không phải cloaking |
| bất kỳ | bị chặn 403/429/captcha | giữ kết luận của người xem |

**Bất đối xứng có chủ đích.** Googlebot *nhận được* nội dung thì tin tuyệt đối —
máy chủ không bao giờ cho Googlebot giả xem nhiều hơn Googlebot thật. Googlebot
*bị chặn* 403/429 thì không tin: nhiều site kiểm tra IP và chỉ chặn Googlebot
giả, mà IP máy chạy tool không phải của Google. Riêng 404/410 thì tin: chặn bot
giả trả 403, không ai trả "trang không tồn tại".

Đo thật ngày 2026-09-17 trên 49 dòng đang ra "Link còn": **37 dòng** trả 200 cho
Chrome, Bingbot, AhrefsBot và curl nhưng trả **404 riêng cho Googlebot** — toàn
bộ là họ directory (`*directory*.com`) và blog farm (`blogzet.com`,
`total-blog.com`…) ở tier 3 và 4. Tier 1, 2 không dính. Chạy lại tier 3 `-n 20`
sau khi nâng cấp: 20/20 ra `GOOGLE_BI_BAO_404`.

Bằng chứng mang đi đòi bù: dán URL vào
[Rich Results Test](https://search.google.com/test/rich-results). Công cụ đó tải
trang từ máy chủ Google, nên gạt được câu "chỉ chặn Googlebot giả thôi".

Ba trường hợp tool cố ý **không** kết luận:
- Link chỉ xuất hiện sau khi render JavaScript (`rendered = playwright`) mà HTML
  thô gửi Googlebot không có — Google cũng render JS. Cột ghi
  `khong ro - link chen bang JavaScript`.
- Googlebot nhận trang gần như trống — có thể là khung chờ JS.
- Người xem thấy link, bản điện thoại gửi Googlebot không có: tool hỏi thêm bản
  máy tính. Kết luận vẫn là mất link (Google index bản điện thoại), nhưng cột
  `googlebot` ghi `khong thay link (ban dien thoai)` để trả lời trước câu
  "trên máy tính vẫn thấy mà".

Không hỏi Googlebot khi: `robots.txt` đã cấm (kết luận không đổi), trang không
phản hồi (DNS, timeout, từ chối kết nối), hoặc mạng máy chạy tool chặn.

Chi phí: thêm 1 request mỗi URL, vẫn xếp hàng theo `per_domain_delay`, nên lượt 1
chậm gần gấp đôi (lượt render không đổi). Tắt bằng `googlebot.check: false`.

### Đọc trang: những chỗ đã vá

- Chỉ thị robots đọc từ cả `<meta name="robots">`, `<meta name="googlebot">` và
  header `X-Robots-Tag` — header viết riêng cho bot khác (`bingbot: noindex`) thì
  bỏ qua. Trước chỉ đọc `meta robots`, hai đường kia cho ra "Link còn" sai.
- `nofollow` / `none` cấp trang làm mọi link thành nofollow dù thẻ `<a>` không
  có `rel`. Cột `rel` ghi rõ `nofollow toan trang (meta robots)`.
- Trang có nhiều link về đích thì chọn link **tốt nhất** (đúng URL > sai URL,
  dofollow > nofollow, hiện > ẩn), không lấy link đầu tiên — một link nofollow ở
  sidebar đứng trước link dofollow trong bài từng biến cả dòng thành `NOFOLLOW`.
- Link là ảnh thì anchor lấy từ `alt`, không còn báo `ANCHOR_RONG` oan.
- `<base href>` được tính khi ghép href tương đối.

### Lượt render chạy song song

Lượt 2 là khâu chậm nhất cả đợt chạy — chiếm khoảng 3/4 tổng thời gian. Nó mở
nhiều tab Chromium cùng lúc, mỗi tab một context riêng để cookie site này không
lẫn sang site kia:

```yaml
js:
  concurrency: auto   # auto | 1..6
```

Dự án hiện tại đang đặt **`concurrency: 6`** (trần cứng). Muốn hạ về mức an
toàn thì sửa đúng dòng đó thành `4` hoặc `auto`, không đụng vào code.

`auto` = `min(4, số CPU // 2)`. Máy 12 nhân ra 4 tab, máy 2 nhân ra 1 tab —
tức đúng bằng hành vi tuần tự cũ, nên tool đem sang máy yếu vẫn chạy được.
Điền tay quá 6 sẽ bị hạ xuống 6 kèm cảnh báo: mỗi tab tốn khoảng 300MB RAM mà
không nhanh thêm bao nhiêu.

**Các tab vẫn tôn trọng `per_domain_delay`.** Nhiều URL cùng một domain phải xếp
hàng y như lượt 1 — không có chuyện 4 tab cùng bắn vào một directory rồi ăn
`HTTP_429` giả. Hàng đợi còn được xếp xen kẽ domain trước khi chia việc, để các
tab không cùng kẹt ở một chỗ (tier 1 có domain `network-316491.mn.co` giữ tới 31
link liền nhau).

Đo trên dự án hiện tại: một lần chạy full 4 tier từ khoảng 4h30 xuống còn
khoảng 1h35.

**Mỗi lần render có trần cứng.** `page.goto()` nhận tham số timeout, nhưng
`page.content()` và `page.evaluate()` thì **không** — API Playwright không có
chỗ khai, hai hàm này chờ vô hạn. Trang có JS chạy liên tục (mn.co, penzu —
đúng những site mục `wait_until` đã cảnh báo là không bao giờ "idle") treo ở đó
mãi mãi được. Worker đang treo vẫn **giữ domain lock**, nên mọi worker khác bốc
phải URL cùng domain sẽ kẹt theo, và cả lượt render đứng hình.

Trần tính bằng `js.timeout + 2 × js.wait_after + 20s` (cấu hình hiện tại: 92
giây). Quá ngưỡng thì vứt tab, ghi `render_that_bai`, đi tiếp. Xem
`_tran_render()` trong [checker.py](src/checker.py).

**Link đã bị `robots.txt` chặn thì không render.** `robots.txt` được đọc xong
ngay từ lượt 1, mà `diagnose()` chốt `ROBOTS_CHAN_GOOGLE` **trước mọi nhánh
khác** — nên với những dòng này, đọc được nội dung hay không cũng ra đúng một
kết luận. Mở Chromium chỉ để vứt kết quả đi. Đo trên lần chạy 2026-09-06: tier 1
có 324 dòng `robots = bi chan`, **293 dòng trong số đó đã tốn công render**, và
cả 324 đều ra `ROBOTS_CHAN_GOOGLE` — không một dòng nào đổi kết luận nhờ render.
Xem `_bo_render_thua()` trong [checker.py](src/checker.py). Console in rõ số lần
đã bỏ qua.

Hàng đợi cũng được **rải đều theo domain**, không phải xếp vòng tròn. Vòng tròn
làm cạn domain nhỏ trước rồi dồn toàn bộ phần còn lại của domain lớn vào cuối
hàng — chính là chỗ mọi worker cùng kẹt vào nhau. Rải đều thì 31 link của
`network-316491.mn.co` trải từ đầu đến cuối, và không có hai mục liên tiếp nào
trùng domain.

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
- gán tier theo hai bước: (1) tên tab có ghi thẳng số tầng — `TANG 2`,
  `Tier 2`, `Tang 4_Bookmarks` — thì lấy luôn số đó, khai báo rõ ràng thắng
  trước; (2) không có thì mới xét `match`, ưu tiên từ khoá dài hơn (nên
  `Submiss Web 2.0 tầng 3` vào tier 3 chứ không rơi vào tier 2 chỉ vì chứa
  chuỗi `web 2.0`). Nhờ bước 1 mà **một file config chạy được với cả tên tab cũ
  lẫn tên tab theo quy ước mới** — lúc chuyển giao không phải sửa gì. Thiếu bước
  đó thì tab `TANG 3 - WEB 2.0` bị kéo về tier 2, vì `web 2.0` (7 ký tự) dài hơn
  `tang 3` (6). Xem `tier_for_sheet()` trong [bl_config.py](src/bl_config.py)

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

Và file `results/<ngày>_<site>_doi-soat.xlsx` gồm 4 sheet:
- **Đối soát** — bảng trên + khối "ĐỀ NGHỊ BÙ LẠI" đã cộng sẵn.
- **Link trùng** — từng URL bị lặp: số lần xuất hiện, tab đặt lần đầu, tab lặp lại,
  trùng chéo tab hay trùng trong cùng một tab.
- **Link chết - gửi họ** — từng URL chết kèm mã lỗi, chẩn đoán, cột **Yêu cầu**
  (`Thay link moi` / `Sua link`) và hai cột **Người xem thấy / Google thấy** làm
  bằng chứng khi họ nói "mở ra vẫn thấy link". Khối "ĐỀ NGHỊ BÙ LẠI" cũng tách
  sẵn bao nhiêu link phải thay mới, bao nhiêu chỉ cần sửa trên bài cũ.
- **Phải check tay** — từng URL tool **chưa kết luận được**, kèm mã lỗi, chẩn đoán
  và cách kiểm tra. Đây là phần việc còn tồn, **không** nằm trong yêu cầu bù.
  Đầu sheet có khối tóm tắt chia theo cột `Ai lam`: nhóm **Chạy lại tool** (xanh)
  xếp trên cùng vì chạy lại một lượt là rụng cả cụm, không tốn công người; nhóm
  **Mở trình duyệt** (vàng) mới phải mở từng URL rồi `Ctrl+F` tìm money site.
  Sheet này trùng nội dung với sheet "Cần check tay" của file `_tier<N>.xlsx`,
  khác ở chỗ gộp cả 4 tier vào một bảng và ghi rõ tab nguồn để đối chiếu với
  bên cung cấp.

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
| Chết khi kiểm tra | 404 / 410 / domain hết hạn / bài bị gỡ / **noindex** / **nofollow** / **canonical khác** / **cần đăng nhập mới xem** / **robots.txt chặn Google** / **Google bị báo 404** / **giấu link với Google** / **vòng lặp chuyển hướng** |
| Không truyền giá trị (phụ) | Mã lỗi chính là chuyện khác nhưng dòng vẫn dính `noindex` / `nofollow` / `canonical khác` — bắt qua cột `canh_bao_them` |

Lưu ý cách đọc khoản **"Không truyền giá trị (phụ)"**: `TRANG_NOINDEX`,
`NOFOLLOW`, `CANONICAL_KHAC` khi là **mã lỗi chính** đã được xếp thẳng vào nhóm
`Link mất` ngay trong file kết quả check, nên chúng rơi vào khoản "Chết khi kiểm
tra". Khoản phụ chỉ còn cộng thêm cho những dòng kết luận là `Link còn` nhưng
vẫn dính một trong ba thứ đó ở cột `canh_bao_them`. Hai đường không chồng nhau,
không đếm trùng.

Nhóm **"phải check tay"** cố ý **không** đưa vào yêu cầu bù: tool chưa đọc được
nội dung thật nên chưa có bằng chứng. Đòi bù bằng số liệu chưa xác minh là tự
làm yếu lập luận của mình. Con số này hiện riêng ở khối "Chưa tính vào yêu cầu bù".

Chưa chạy check bao giờ thì cột `Chết` bằng 0 và tool cảnh báo rõ — đó là vì
chưa đo, không phải vì không có link chết.

## File gốc có chú thích

Ba file trong `results/` trả lời ba câu hỏi khác nhau:

| File | Trả lời |
|------|---------|
| `<ngày>_<site>_tier<N>.xlsx` | Link nào hỏng, hỏng vì gì — danh sách **đã làm sạch**, gộp mọi tab thành một bảng |
| `<ngày>_<site>_doi-soat.xlsx` | Họ giao bao nhiêu, ta nhận bao nhiêu, đòi bù bao nhiêu |
| `<ngày>_<site>_goc-chu-thich.xlsx` | **Chính file bên cung cấp gửi**, giữ nguyên từng tab từng dòng, mỗi dòng thêm chú thích |

File thứ ba sinh ra ở bước 5 của `blcheck run`, hoặc chạy riêng:

```powershell
.\blcheck.bat ghichu
```

Nó tải lại nguồn gốc, **không gộp tab, không lọc dòng nào**, chỉ thêm 3 cột vào
sau cột cuối cùng của mỗi tab:

| Cột thêm | Nội dung |
|----------|----------|
| `Ket luan` | Link còn / Link mất / Phải check tay / Trùng lặp / Link của mình / URL hỏng / Chưa check |
| `Ma loi` | Mã lỗi, để lọc trong Excel |
| `Chu thich` | Chẩn đoán + việc cần làm + cảnh báo thêm + mã HTTP |

Chỉ phần chú thích được tô màu, dữ liệu gốc giữ nguyên:

| Màu | Nghĩa |
|-----|-------|
| xanh lá | Link còn, dùng được |
| đỏ | Link mất — gồm cả noindex, nofollow, canonical khác |
| vàng | Chưa kết luận được, phải mở tay |
| cam | Bị loại ngay từ bước làm sạch: trùng lặp, trỏ về money site, ô không phải URL, domain bị loại |
| xám | Không tính (cột ngoài `sheet_columns`) hoặc chưa chạy check tới |

Điểm mạnh của file này là **giải thích được những dòng biến mất khỏi
`backlinks_master.csv`**. Ví dụ tab `Tang 4_Bookmarks`: 418 dòng tô cam ghi rõ
"URL này đã xuất hiện trước đó ở tab `Tang 4_Blog Comment`" — nhìn ngay trên file
quen thuộc, không phải đối chiếu hai bảng.

Một dòng có nhiều URL (tab 2 cột link) thì cột `Ket luan` ghi tổng hợp
(`2 link: 1 Link còn, 1 Link mất`) và tô màu theo link xấu nhất; cột `Chu thich`
liệt kê từng link. Sheet đầu tiên `Doc truoc` là bảng chú giải kèm số lượng từng
nhãn.

Chạy `run -n 20` thì phần lớn dòng mang nhãn "Chưa check" — đúng, vì mới check 20
link đầu mỗi tier.

Thứ tự quét trùng lặp giống hệt `ingest.py`: lần xuất hiện **đầu tiên** được giữ,
các lần sau mới bị đánh dấu trùng. Nên tab nào bị coi là bản sao phụ thuộc thứ tự
tab trong Google Sheet.

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
| Link còn | xanh lá | **Googlebot** đọc được trang, **nhìn thấy thẻ `<a>`**, link dofollow và trang index được — tức là link **truyền được giá trị** | Không cần mở tay. Xem `muc_do` để biết link tốt hay còn khiếm khuyết. Nhóm này gồm cả `TRO_SAI_TANG`, `SAI_URL_DICH` (vào sai chỗ), `CLOAKING_NGUOI_DUNG` (người dùng bị chuyển đi nhưng Google vẫn thấy link), `NHANH_TREN_DA_CHET` và `LINK_BI_AN` |
| Link mất | đỏ | Tool đọc được trang và chắc chắn link **không truyền được giá trị nào**: 404/410/domain hết hạn/bài bị gỡ, thẻ `<a>` vẫn còn nhưng **noindex / nofollow / canonical khác**, hoặc **người xem thấy link mà Googlebot thì không** | Không cần mở tay. Đòi bù hoặc thay nguồn mới — xem cột `yeu_cau` |
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
- `robots` — `cho phep` / `bi chan` / `khong ro`, đọc từ `robots.txt` của site
  nguồn. `bi chan` nghĩa là Googlebot không được phép vào URL đó. `khong ro` là
  chưa đọc được file (mất mạng, 403, 5xx) — tool **không** kết luận gì từ đó.
- `rendered` — `http` hay `playwright`. Kết luận "mất link" từ dòng `http` trên
  một domain render JS là không đáng tin.
- `nguoi_xem` / `googlebot` — hai góc nhìn đặt cạnh nhau, viết bằng cụm từ ngắn
  (`thay link`, `bi bao 404`, `bi chuyen sang ...`, `khong ro - bi chan HTTP 403`).
  Trong XLSX nằm ngay sau cột Kết luận; hai ô **tô đỏ đậm** là chỗ người xem và
  Google thấy khác nhau. Xem mục "Googlebot là chuẩn".
- `yeu_cau` — `Thay link moi` (phải đăng bài khác) / `Sua link` (bên cung cấp sửa
  ngay trên bài cũ: đổi dofollow, đổi đích, mở công khai) / `Sua tang tren`.
  Bảng ánh xạ ở `LOAI_YEU_CAU` trong [diagnose.py](src/diagnose.py).
- `dich_tang_tren` — link tier 3/4 trỏ vào URL tầng trên: URL đó `con song` hay
  `DA CHET (<mã>)`. Xem mục "Nhánh tầng trên đã chết".
- `vi_tri_link` — `than bai` / `binh luan` / `ho so` / `sidebar` / `footer` /
  `menu` / `khong ro`. Phần tử cha **gần nhất** quyết định. Chỉ để tham khảo,
  không đổi kết luận.

### Nhánh tầng trên đã chết

Tool check từng link độc lập, nhưng giá trị chạy theo chuỗi tầng 3 → tầng 2 →
money site. Link tầng 3 nguyên vẹn mà URL tầng 2 nó trỏ tới đã chết thì giá trị
dừng lại ở đó. [nhanh.py](src/nhanh.py) nối các tầng lại sau khi check xong mỗi
tier: tra kết luận của URL tầng trên trong chính đợt chạy này, thiếu thì lấy từ
CSV mới nhất trong `results/`.

Dòng bị đánh dấu mang mã `NHANH_TREN_DA_CHET`, vẫn là **Link còn** và **không**
vào yêu cầu bù — không phải lỗi của bên đặt link tầng dưới. Console và sheet
"Tổng hợp" liệt kê URL tầng trên đã chết kèm số link tầng dưới đang đổ vào nó:
sửa URL nào trước thì cứu được nhiều link nhất.

Vì `blcheck run` chạy theo `priority` (tier 2 → 1 → 3 → 4), tầng trên luôn có kết
quả trước tầng dưới. Chạy riêng `-t 4` thì tool dùng CSV tier 3 lần gần nhất.

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
| `SOFT_404` | 200 nhưng title là trang lỗi, hoặc trang ngắn không có link mà nội dung ghi rõ "không tồn tại" / "page not found" | Coi như mất link |
| `DOMAIN_RAO_BAN` | nội dung là trang parking/rao bán | Bỏ. Có thể độc hại |
| `CHUYEN_VE_TRANG_CHU` | bài viết bị redirect về trang chủ | Dấu hiệu bài bị gỡ |
| `TRANG_NOINDEX` | `meta robots` / `meta googlebot` / header `X-Robots-Tag` có noindex, thẻ `<a>` vẫn còn | **Coi như mất link.** Google không đọc tới trang nên thẻ `<a>` không truyền được chút giá trị nào. Có tính vào khoản đòi bù |
| `NOFOLLOW` | rel nofollow/ugc/sponsored, hoặc `nofollow` cấp trang trong meta robots / `X-Robots-Tag` | **Coi như mất link.** Thẻ `<a>` còn đó nhưng Google không truyền chút sức mạnh nào. Đòi đổi sang dofollow hoặc bù. Có tính vào khoản đòi bù |
| `CANONICAL_KHAC` | canonical trỏ đi nơi khác | **Coi như mất link.** Google gộp trang vào bản canonical, giá trị chảy sang chỗ khác. Có tính vào khoản đòi bù |
| `ROBOTS_CHAN_GOOGLE` | `robots.txt` của site có dòng `Disallow` khớp đường dẫn này | **Coi như mất link.** Trang mở bình thường với người, thẻ `<a>` còn nguyên, nhưng Googlebot bị cấm thu thập nên không truyền giá trị. Bằng chứng đòi bù rất mạnh: dán nguyên dòng `Disallow` trong `robots.txt` của chính họ. Có tính vào khoản đòi bù |
| `VONG_LAP_CHUYEN_HUONG` | trang chuyển hướng vòng tròn, cả httpx lẫn Chromium đều không mở được | Coi như mất link. Có tính vào khoản đòi bù |
| `GOOGLE_BI_BAO_404` | người xem thấy link, Googlebot nhận 404/410 hoặc trang báo lỗi | **Coi như mất link.** Trang giấu mình với riêng Google. Bằng chứng: Rich Results Test. Có tính vào khoản đòi bù |
| `AN_LINK_VOI_GOOGLE` | người xem thấy link, trang gửi Googlebot không có thẻ `<a>` hoặc chuyển Googlebot đi chỗ khác | **Coi như mất link.** Có tính vào khoản đòi bù |
| `CAN_DANG_NHAP_MOI_XEM` | đã render bằng Chromium mà trang vẫn đòi đăng nhập | **Coi như mất link.** Googlebot không có tài khoản nên không vào được — đăng nhập tay chỉ xác nhận bài còn, không làm link truyền được giá trị. Việc cần làm là đổi chế độ chia sẻ sang công khai. Có tính vào khoản đòi bù |

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
| `TUONG_DANG_NHAP` | lượt HTTP thô đòi đăng nhập, chưa render | Chạy lại có render. Vẫn đòi đăng nhập thì thành `CAN_DANG_NHAP_MOI_XEM` |
| `SSL_LOI` | chứng chỉ hỏng | Trang có thể vẫn sống, xác nhận tay |
| `MANG_CUA_BAN_CHAN` | DNS của máy trả về `127.0.0.1`, tool đã vá bằng địa chỉ thật mà đường truyền vẫn cắt kết nối | **Nói về máy chạy tool, không nói về link.** Googlebot thu thập từ hạ tầng Google, không đi qua mạng này. Đừng thay nguồn, đừng đưa vào yêu cầu bù. Muốn đọc nội dung thì đổi 4G/VPN rồi chạy lại tier đó |

### Link mất giá trị dù vẫn tồn tại

| Mã | Tín hiệu | Xử lý |
|----|----------|-------|
| `LINK_BI_GO` | trang sống, đọc được nội dung thật, không còn thẻ `<a>` nào về hệ thống mình | Admin gỡ link. Đăng lại |
| `TRO_SAI_TANG` | link còn, trỏ đúng hệ thống mình nhưng **sai tầng** so với khai báo | Không phải link hỏng. Sửa khai báo `targets` cho khớp thực tế, hoặc đặt lại link |
| `SAI_URL_DICH` | đúng domain, sai trang | Sửa về đúng URL nếu còn quyền |
| `LINK_QUA_TRUNG_GIAN` | href đi qua rút gọn/redirect | Ưu tiên link trỏ thẳng |
| `TRANG_NHIEU_LINK_RA` | vượt `thresholds.outbound_link_limit` | Đặc trưng link farm |
| `ANCHOR_RONG` / `ANCHOR_LA_URL` | anchor rỗng hoặc là URL trần | Không gấp |
| `CLOAKING_NGUOI_DUNG` | Googlebot thấy link, người dùng bị chuyển đi / thấy 404 / không thấy link | **Vẫn là Link còn**, mức GHI CHÚ. Không đòi bù. Site dùng cloaking có rủi ro bị phạt, không đầu tư thêm |
| `NHANH_TREN_DA_CHET` | link còn nhưng URL tầng trên nó trỏ vào đã chết | Vẫn là Link còn, không đòi bù. Sửa URL tầng trên trước |
| `LINK_BI_AN` | thẻ `<a>` nằm trong phần tử `display:none` / `visibility:hidden` / cỡ chữ 0 (style inline) | Vẫn là Link còn vì có thể nhầm với tab / accordion đóng sẵn. Mở trang xem rồi mới đòi sửa |

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
  retries: 1             # chỉ áp cho lỗi kết nối, KHÔNG áp cho timeout

js:
  concurrency: auto      # số tab Chromium song song ở lượt render
```

Nếu đặt `per_domain_delay` dưới 1.0, tool in cảnh báo ngay khi khởi động.

### `retries` không áp cho timeout

`retries` chỉ thử lại khi **lỗi kết nối** (`ConnectError`, SSL, reset) — loại
thất bại trong chưa tới một giây nên thử lại gần như miễn phí và hay cứu được.

Gặp **timeout** thì tool bỏ luôn lượt thử lại. Một lần timeout đã trả trọn 25
giây; bắn lại y hệt thao tác vừa thất bại là khoản đắt nhất cả đợt chạy mà hiếm
khi đổi được kết quả. Link đó vẫn còn một lượt nữa: nó được đẩy sang Chromium ở
lượt 2 (xem `_nen_render(..., loi_ket_noi=True)` trong
[checker.py](src/checker.py)), mà trình duyệt thật mạnh hơn httpx lặp lại nhiều.

Hệ quả cần biết: **máy chưa cài Playwright** thì link timeout đi thẳng tới
`CHUA_CAI_PLAYWRIGHT` thay vì có cơ hội được lượt retry cứu. Tool vẫn không kết
luận mất link — chỉ chuyển sang "phải check tay".

## Khi router hoặc nhà mạng chặn tên miền

Một số router và nhà mạng trả về `127.0.0.1` cho tên miền bị chặn. `127.0.0.1`
là **chính máy đang chạy tool** — nên tool gõ cửa chính nó rồi báo
`KET_NOI_TU_CHOI`, trong khi link ngoài đời vẫn sống.

Đo thật ngày 2026-09-06 trên một máy chạy tool:

```
huthamctp.jimdosite.com  →  127.0.0.1        (hỏi router 192.168.0.1)
                         →  162.159.129.70   (hỏi 8.8.8.8, địa chỉ thật)
```

Cả **24 dòng** `KET_NOI_TU_CHOI` trong đợt chạy hôm đó đều là chuyện này, trên
5 tên miền: `hackmd.io`, `g0v.hackmd.io`, `medium.com`, `band.us`,
`huthamctp.jimdosite.com`. Không một trường hợp từ chối kết nối thật nào.

Tool tự xử lý, người dùng không phải đụng vào cài đặt máy — xem
[dnsfix.py](src/dnsfix.py):

1. Trước khi tải trang, kiểm tra tên miền có bị phân giải về `127.0.0.1` không.
2. Nếu có, hỏi lại qua **DNS-over-HTTPS** (đi thẳng qua HTTPS nên router không
   xen vào được).
3. Ép `socket.getaddrinfo` dùng địa chỉ thật. HTTPS vẫn an toàn: SNI và header
   `Host` lấy từ URL chứ không lấy từ `getaddrinfo`, chứng chỉ vẫn được kiểm
   tra đúng tên miền.
4. Chromium chạy ở tiến trình riêng nên được truyền cùng bảng địa chỉ đó qua
   `--host-resolver-rules`.

Tắt bằng `network.dns_fallback: false` — chỉ nên tắt khi máy nằm trong mạng nội
bộ dùng split-DNS hợp lệ.

**Vì sao phải vá ở tầng DNS chứ không chỉ đổi tên mã lỗi.** Nếu máy đang chạy
bất kỳ web server nào nghe cổng 443 (XAMPP, Docker, một dev server bỏ quên),
local server sẽ **trả lời thay** cho tên miền bị bắt cóc. Tool nhận HTTP 200,
đọc một trang HTML lạ, không thấy thẻ `<a>` nào về money site, rồi kết luận
`LINK_BI_GO` — *"admin đã gỡ link, đăng lại"*. Sai hoàn toàn, tô đỏ, tính vào
tiền đòi bù, và **không có dấu hiệu gì để nhận ra**. Vá từ tầng DNS thì cả hai
kiểu hỏng — ồn ào và im lặng — đều biến mất.

**Giới hạn.** Chỉ vá được kiểu chặn bằng DNS. Nếu đường truyền còn lọc theo tên
miền — nối được tới IP thật nhưng vừa khai tên miền là bị cắt — thì không tool
nào vượt qua được. Trường hợp đó ra mã `MANG_CUA_BAN_CHAN`.

### `MANG_CUA_BAN_CHAN` không phải lỗi của link

Tool trả lời câu hỏi **"Googlebot có vào được và có nhận được giá trị không"**,
không phải "máy tôi có mở được trang không". Hai câu đó khác nhau, và mã này
nằm đúng chỗ khác nhau đó.

Googlebot thu thập từ hạ tầng của Google, **không đi qua mạng đang chạy tool**.
Đo được: máy chủ vẫn sống — nối tới IP thật thành công ở tầng TCP, và bắt tay
TLS cũng thành công nếu khai một tên miền khác. Chỉ riêng kết nối khai đúng tên
miền mới bị cắt, và bị cắt ở đường truyền nội địa. Nên khả năng Google vẫn thu
thập bình thường là rất cao.

Vì vậy:

- Mức độ là **GHI CHÚ**, không phải CẢNH BÁO hay NẶNG.
- Mã này **đứng ngoài `bump_by_tier`** (xem `MA_MOI_TRUONG` trong
  [diagnose.py](src/diagnose.py)). Nếu không, một link tier 2 (`priority: 1`) mà
  tool không đọc được vì mạng nhà sẽ bị đẩy lên NẶNG màu cam — trông y như link
  đang hỏng, trong khi thực tế chưa đo được gì về nó.
- **Không** tính vào yêu cầu bù, và việc cần làm ghi rõ là đừng thay nguồn.

Cái vẫn chưa biết là **thẻ `<a>` còn trên trang hay không** — vì tool chưa đọc
được nội dung lần nào. Đó là khoảng trống của phép đo, không phải khuyết điểm
của link. Muốn lấp thì đổi 4G/VPN rồi chạy lại tier đó.

Kết quả đo lại trên đúng 24 link đó sau khi vá:

| Tên miền | Trước | Sau |
|---|---|---|
| `hackmd.io` (9) | `KET_NOI_TU_CHOI` | `TRANG_RONG` — đã đọc được site thật |
| `g0v.hackmd.io` (3) | `KET_NOI_TU_CHOI` | 1 `OK`, 2 `MANG_CUA_BAN_CHAN` |
| `medium.com` (4), `band.us` (5), `jimdosite` (3) | `KET_NOI_TU_CHOI` | `MANG_CUA_BAN_CHAN` |

Vì tool được dùng chung trên nhiều máy, **cùng một danh sách link chạy ở hai
mạng khác nhau sẽ ra kết quả khác nhau**. Mã `MANG_CUA_BAN_CHAN` tồn tại để chỗ
lệch đó hiện ra thành chữ, thay vì lẫn vào đống "link chết".

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
Ahrefs / Majestic.

Cần phân biệt ba câu hỏi gần giống nhau:
- **"Google có được phép vào không"** — tool trả lời được: đọc `robots.txt`, ra
  mã `ROBOTS_CHAN_GOOGLE`.
- **"Site trả gì cho Googlebot"** — tool trả lời được ở mức User-Agent: tải lại
  bằng UA Googlebot, ra `GOOGLE_BI_BAO_404` / `AN_LINK_VOI_GOOGLE`. Không giả
  được IP của Google, nên site nào xác minh IP thì phải kiểm chứng bằng Rich
  Results Test.
- **"Google đã thực sự index chưa"** — tool không trả lời được, vì được phép vào
  không có nghĩa là đã vào.
Phần lớn giá trị nằm ở câu hỏi thứ nhất, nhưng đừng đọc nhầm cái này thành cái kia. Link tồn tại nhưng trang không được index thì gần như không
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
