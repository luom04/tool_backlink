# Hướng dẫn cấu hình — dành cho người dùng, không cần biết code

File bạn cần sửa: **`config/checkbacklink.yaml`**. Mở bằng Notepad hoặc VS Code
đều được. Không đụng gì tới thư mục `src/`.

Vài quy tắc của file `.yaml` — nhớ 4 điều này là đủ:

1. **Thụt đầu dòng bằng dấu cách, không bằng phím Tab.** Đây là lỗi hay gặp nhất.
2. Dấu `#` mở đầu một dòng nghĩa là dòng ghi chú, tool bỏ qua.
3. Dấu hai chấm phải có khoảng trắng sau nó: viết `name: abc`, không viết `name:abc`.
4. Dòng bắt đầu bằng `- ` là một mục trong danh sách.

Sửa xong, kiểm tra file có hợp lệ không bằng lệnh:

```powershell
.\blcheck.bat ingest --dry-run
```

Báo lỗi gì thì nó nói rõ sai ở tier nào, mục nào.

---

## Phần 1 — Khai báo website của bạn

```yaml
site:
  name: huthamcautienphat
  money_domain: huthamcautienphat.com

  target_urls:
    - https://huthamcautienphat.com/dich-vu-hut-ham-cau
    - https://huthamcautienphat.com/hut-ham-cau-tai-tp-hcm-binh-duong

  extra_domains: []
```

| Dòng | Điền gì |
|---|---|
| `name` | Tên ngắn của dự án. Dùng để đặt tên file kết quả. Không dấu, không khoảng trắng. |
| `money_domain` | Website chính cần nhận backlink. Không cần `https://`, không cần `www.` |
| `target_urls` | Các trang đích cụ thể trong kế hoạch. Link trỏ đúng domain nhưng sai trang sẽ bị đánh dấu `SAI_URL_DICH`. Để trống nếu chỉ cần đúng domain là được. |
| `extra_domains` | Domain phụ bạn cũng sở hữu (`.vn`, `.net`, domain rút gọn riêng). Link trỏ về đây cũng tính là backlink hợp lệ. |

---

## Phần 2 — Dán link Google Sheet

```yaml
source:
  type: auto
  url: "https://docs.google.com/spreadsheets/d/1Mofu08.../edit"
```

Dán nguyên link trên thanh địa chỉ trình duyệt, không cần cắt bớt phần đuôi.

**Bắt buộc:** mở file đó trên Google Sheets → nút **Share** → mục **General
access** → chọn **"Anyone with the link"** → quyền **Viewer**. Không làm bước này
thì Google chặn và tool báo lỗi 403.

---

## Phần 3 — Khai báo các tầng

Đây là phần quan trọng nhất, và cũng là chỗ dễ khai sai nhất.

```yaml
tiers:
  1:
    label: "Tier 1 - tro thang money site"
    targets: money
    priority: 2
    match:
      - "backlink domain dr cao"
      - "tang 1"

  3:
    label: "Tier 3"
    targets: ["tier:2", money, "tier:3"]
    priority: 4
    match:
      - "tang 3"
```

### `match` — tool nhận ra tab nào thuộc tầng nào

Ghi vào đây vài từ khoá có trong **tên tab** của Google Sheet. Tool so khớp
kiểu "tên tab có chứa chuỗi này không", **không phân biệt hoa thường, không
phân biệt dấu tiếng Việt**. Nên viết `"tang 3"` là khớp được cả `Tầng 3`.

Nếu một tên tab khớp nhiều tầng thì **từ khoá dài hơn thắng**. Ví dụ tab
`Submiss Web 2.0 tầng 3` sẽ vào tier 3 (khớp `"submiss web 2.0"`, 16 ký tự) chứ
không rơi vào tier 2 (chỉ khớp `"web 2.0"`, 7 ký tự).

Chạy `.\blcheck.bat ingest --dry-run` để xem tab nào được xếp vào tầng nào. Có
tab bị báo "không khớp tier nào" thì thêm từ khoá rồi chạy lại.

### `targets` — link của tầng này phải trỏ về đâu

Đây là câu hỏi: *"tool coi link này là đạt khi nó trỏ vào đâu?"*

Có hai loại đích:

| Viết | Nghĩa |
|---|---|
| `money` | Trỏ thẳng về website chính |
| `"tier:2"` | Trỏ về bất kỳ URL nào thuộc tier 2 |

Khai một đích:

```yaml
targets: money
```

Khai nhiều đích — dùng ngoặc vuông, ngăn nhau bằng dấu phẩy:

```yaml
targets: ["tier:2", money]
```

Nghĩa là: *link của tầng này trỏ về tier 2 **hoặc** trỏ thẳng money site đều được
tính là còn sống.*

**Đích đầu tiên trong danh sách là đích bạn kỳ vọng.** Link rơi vào đích đầu
tiên thì tốt. Link rơi vào đích thứ hai, thứ ba thì vẫn tính là **còn sống**,
nhưng tool gắn mã `TRO_SAI_TANG` để bạn biết cấu trúc thực tế đang lệch so với
kế hoạch. Cột **"Khớp tầng"** trong file kết quả ghi rõ nó trỏ vào tầng nào.

Quy tắc: link chỉ được trỏ **lên tầng trên hoặc trong cùng một tầng**. Khai
`targets: "tier:4"` cho tier 3 sẽ bị báo lỗi ngay.

> **Vì sao nên khai nhiều đích?**
> Vì sơ đồ trên giấy hiếm khi khớp thực tế. Khai đúng một đích thì mọi link
> trỏ đi chỗ khác đều bị báo là **mất link**, dù nó vẫn sống nguyên. Khai nhiều
> đích thì tool nói đúng bản chất: *"link còn, nhưng trỏ vào tầng khác"*.

### `priority` — mức độ quan trọng của tầng

Số nhỏ hơn = quan trọng hơn. Nó chỉ ảnh hưởng tới màu tô trong file Excel:

| Giá trị | Tác dụng |
|---|---|
| `1` | Lỗi ở tầng này bị **nâng lên một bậc** nghiêm trọng |
| `2` hoặc `3` | Giữ nguyên |
| `4` trở lên | **Hạ xuống một bậc** — chỉ theo dõi tổng quan |

Đặt `priority: 1` cho tầng mà nếu mất một link là kéo sập cả nhánh bên dưới.

---

## Phần 4 — Render JavaScript

Nhiều nền tảng (Penzu, Notion, Wakelet, mn.co…) trả về trang trống rồi mới dùng
JavaScript vẽ nội dung vào sau. Đọc kiểu thường thì không thấy link nào, tool sẽ
tưởng link đã bị gỡ. Phải mở bằng trình duyệt thật (Chromium) mới đọc được.

```yaml
js:
  auto_tiers: []
  escalate: true

  force_domains:
    - "penzu.com"
    - "notion.site"
    - ".mn.co"

  wait_until: domcontentloaded
  wait_after: 6000
  timeout: 60000
```

| Dòng | Ý nghĩa |
|---|---|
| `escalate: true` | **Để nguyên.** Tool chạy hai lượt: lượt 1 đọc nhanh toàn bộ, lượt 2 chỉ mở trình duyệt cho những link chưa đọc được. Nhanh hơn nhiều so với mở trình duyệt cho tất cả. |
| `auto_tiers` | Để trống `[]` là tốt nhất — tool tự quyết. Chỉ điền khi muốn ép một tầng **luôn** render, ví dụ `auto_tiers: [2]` |
| `force_domains` | Danh sách domain **chắc chắn** cần trình duyệt. Thêm vào đây thì không phải chờ lượt 2. |
| `wait_until` | Để `domcontentloaded`. **Đừng đổi thành `networkidle`** — nhiều trang không bao giờ "đứng yên" nên sẽ treo cho tới lúc hết giờ. |
| `wait_after` | Chờ thêm bao nhiêu mili giây cho JS vẽ xong. `6000` = 6 giây. Trang nặng thì tăng lên `10000`. |

### Khi nào cần thêm domain vào `force_domains`?

Mở file kết quả `.xlsx`, lọc cột **"Mã lỗi"** = `LINK_BI_GO`. Nếu thấy nhiều
link cùng một domain đều báo mất, mở thử một cái bằng trình duyệt — link vẫn còn
thì thêm domain đó vào `force_domains` rồi chạy lại.

Viết domain có dấu chấm ở đầu (`.mn.co`) để khớp mọi tên miền con.

### Bắt buộc cài trước

```powershell
pip install playwright
playwright install chromium
```

Thiếu bước này, các link cần render sẽ mang mã `CHUA_CAI_PLAYWRIGHT` — tool
**không** kết luận là mất link, nhưng cũng chưa đọc được nội dung thật.

---

## Một chỗ dễ hiểu nhầm: link noindex

Trang có thẻ `noindex` nghĩa là chủ trang bảo Google **đừng đưa trang này vào
kết quả tìm kiếm**. Google không index trang thì cũng không tính link nằm trên
đó — backlink coi như vô tác dụng.

Tool xử lý trường hợp này ở **hai chỗ khác nhau**, đừng nhầm:

| Ở đâu | Xếp vào nhóm nào | Vì sao |
|---|---|---|
| File kết quả check `.xlsx` | **Link còn** (xanh lá), mức độ NẶNG | Tool nhìn thấy thẻ `<a>` bằng mắt thường. Bạn **không cần mở tay** kiểm tra lại. |
| File đối soát với bên cung cấp | **Có tính vào khoản đòi bù** | Mua backlink là mua giá trị truyền về, không phải mua một thẻ `<a>` nằm trên trang Google không đọc tới. |

Nói cách khác: *"link vẫn nằm đó"* và *"link có dùng được không"* là hai câu hỏi
riêng. Tool trả lời cả hai, ở hai file khác nhau.

Trong file đối soát, cột **"Noindex"** đếm số này, và sheet **"Link chết - gửi họ"**
liệt kê từng URL — dòng đỏ là link đã chết, dòng vàng là link noindex.

---

## Phần 5 — Tốc độ và độ an toàn

```yaml
network:
  concurrency: 8
  per_domain_delay: 1.5
  timeout: 25
  retries: 1
  verify_ssl: false
```

| Dòng | Nên để | Ghi chú |
|---|---|---|
| `concurrency` | `8` | Số link chạy cùng lúc. Mạng khoẻ thì tăng lên 15. Càng cao càng dễ bị chặn IP. |
| `per_domain_delay` | `1.5` | Giây nghỉ giữa hai lần gọi cùng một domain. **Không hạ dưới 1.0.** Nhiều link tầng dưới nằm chung vài domain, bắn nhanh sẽ bị ban IP và cho ra hàng loạt lỗi `HTTP_429` giả. |
| `timeout` | `25` | Giây chờ tối đa mỗi link. |
| `js.timeout` | `60000` | Mili giây chờ tối đa khi mở bằng Chromium. Quá hạn thì link mang mã `CHUA_RENDER_DUOC` và được xếp vào **"phải check tay"** — tool không kết luận là mất link. |
| `retries` | `1` | Số lần thử lại khi timeout. |
| `verify_ssl` | `false` | Nhiều site vệ tinh có chứng chỉ hết hạn, bật lên sẽ bị lỗi oan. |

---

## Phần 6 — Làm sạch dữ liệu khi nạp

```yaml
ingest:
  drop_sheets:
    - "sheet1"
    - "huong dan"

  sheet_columns:
    "link page rank cao": ["link dat"]
```

`drop_sheets` — tab nào có chứa từ khoá này thì bỏ qua hoàn toàn. Dùng cho tab
hướng dẫn, tab nháp, tab của dự án khác.

`sheet_columns` — dùng khi **một tab có nhiều cột URL mà chỉ một cột là backlink
thật**. Ví dụ tab `Link page rank cao` có cột `Tên Miền` (chỉ là trang chủ) và
cột `Link Đặt` (backlink thật). Không khai báo thì tool lấy cả hai, số link bị
phồng lên gấp đôi.

Cách viết: `"từ khoá trong tên tab": ["tên cột ở dòng tiêu đề"]`

Tab có 2 cột URL mà **cả hai** đều là backlink thật thì **đừng** khai báo — cứ để
tool quét hết.

**Dấu hiệu đang lấy nhầm cột:** cuối phần chạy có cảnh báo *"URL chỉ có tên miền,
không có đường dẫn"*. Không phải lúc nào cũng sai — có site đặt link ngay trang
chủ. Nhưng thấy `https://www.tripadvisor.com` trần thì chắc chắn là nhầm cột.

---

## Thêm một dự án mới

1. Copy `config/_mau.yaml` thành `config/tenduan.yaml`
2. Sửa `site`, `source`, và từ khoá `match` của từng tầng
3. Chạy `.\blcheck.bat ingest -c config/tenduan.yaml --dry-run` để xem tab vào đúng tầng chưa
4. Chạy `.\blcheck.bat run -c config/tenduan.yaml -n 20` thử 20 link mỗi tầng
5. Số liệu hợp lý thì chạy thật: `.\blcheck.bat run -c config/tenduan.yaml`

Không phải sửa dòng code nào.

---

## Ba lỗi hay gặp

**"could not find expected ':'" hoặc "found character that cannot start any token"**
→ Bạn thụt đầu dòng bằng phím Tab. Thay bằng dấu cách.

**"tier 3 khong the tro ve tier 4 - do la tang duoi"**
→ Trong `targets` bạn khai một tầng có số lớn hơn. Link chỉ được trỏ lên trên
hoặc ngang hàng.

**Cả tab bị báo "không khớp tier nào"**
→ Thêm từ khoá lấy từ tên tab thật vào `match` của tầng tương ứng. Nhớ là so
khớp theo "chứa chuỗi con", nên chỉ cần một mẩu đặc trưng là đủ.
