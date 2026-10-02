"""
Chuan doan loi cho tung backlink.

Checker chi thu thap tin hieu tho (ma HTTP, ten exception, tieu de trang,
the meta, thuoc tinh cua the <a>...). Module nay bien tin hieu do thanh mot
ma loi ngan gon + cau giai thich tieng Viet + viec can lam.

Muc nghiem trong (severity), dung de to mau trong file XLSX:
    1 CHET      do dam   - link mat han, phai thay nguon moi
    2 NANG      do cam   - link con nhung dang hong, phai xu ly som
    3 CANH BAO  vang     - link con, gia tri thap hon ky vong
    4 GHI CHU   xanh nhat- khong sai, chi de biet
    5 TOT       xanh la  - khong can lam gi
"""

import re

SEV_CHET, SEV_NANG, SEV_CANHBAO, SEV_GHICHU, SEV_TOT = 1, 2, 3, 4, 5

SEV_LABEL = {1: "CHET", 2: "NANG", 3: "CANH BAO", 4: "GHI CHU", 5: "TOT"}

SOFT_404_PAT = re.compile(
    r"(404|not\s*found|page\s+not\s+found|trang\s+kh(o|ô)ng\s+t(o|ồ)n\s+t(a|ạ)i|"
    r"n(o|ộ)i\s*dung\s+(da|đã)\s+b(i|ị)\s+x(o|ó)a|no\s+longer\s+available|"
    r"da\s+b(i|ị)\s+g(o|ỡ)|deleted|removed by)", re.I)

# Soft-404 nhan ra tu THAN trang, khi title van chi la ten site. Chat hon
# SOFT_404_PAT rat nhieu (khong co "404", "deleted" tran) vi than bai viet that
# hoan toan co the chua nhung chu do - va chi dung cho trang NGAN, khong co link.
SOFT_404_THAN_PAT = re.compile(
    r"(page\s+(you\s+(were|are)\s+looking\s+for|you\s+requested|could\s*n[o']?t\s+be\s+found|"
    r"cannot\s+be\s+found|does\s*n[o']?t\s+exist|does\s+not\s+exist|not\s+found)|"
    r"(this|the)\s+(page|post|article)\s+(is\s+)?(no\s+longer\s+available|does\s*n[o']?t\s+exist|"
    r"does\s+not\s+exist|has\s+been\s+(removed|deleted))|"
    r"(sorry|oops)[,!.]?\s+(we\s+)?(could\s*n[o']?t|can\s*n?[o']?t)\s+find|"
    r"kh(o|ô)ng\s+t(i|ì)m\s+th(a|ấ)y\s+(trang|b(a|à)i)|"
    r"(trang|b(a|à)i\s+vi(e|ế)t)\s+(n(a|à)y\s+)?kh(o|ô)ng\s+(c(o|ò)n\s+)?t(o|ồ)n\s+t(a|ạ)i|"
    r"n(o|ộ)i\s*dung\s+(da|đã)\s+b(i|ị)\s+x(o|ó)a)", re.I)

PARKED_PAT = re.compile(
    r"(domain\s+(is\s+)?for\s+sale|buy\s+this\s+domain|t(e|ê)n\s+mi(e|ề)n\s+n(a|à)y\s+"
    r"(dang\s+)?(duoc\s+)?rao\s+b(a|á)n|parked\s+(free|domain)|expired\s+domain|"
    r"this\s+domain\s+(has\s+)?expired|godaddy.*parking)", re.I)

LOGIN_PAT = re.compile(
    r"(dang\s*nh(a|ậ)p\s+(de|để)\s+(xem|ti(e|ế)p)|(please\s+)?(log|sign)\s*in\s+to\s+"
    r"(view|continue|see)|members\s+only|c(a|ầ)n\s+(dang\s*nh(a|ậ)p|tai\s+kho(a|ả)n))",
    re.I)

CAPTCHA_PAT = re.compile(
    r"(cloudflare|just a moment|checking your browser|captcha|are you (a )?human|"
    r"ddos.?guard|attention required|access denied|akamai|请稍候|"
    # WAF doi moi: khong con dung chu "captcha" nua ma bao thang la dang xac
    # minh trinh duyet. Thieu nhung mau nay thi ofuse.me / vercel bi tut xuong
    # TRANG_RONG - sai han ban chat, vi trang do nguoi mo tay van xem duoc.
    r"security checkpoint|vercel security|security verification|"
    r"(failed to )?verify (your |you are using a )?browser|verifying you are human|"
    r"perimeterx|datadome|incapsula|bot protection|"
    r"enable javascript and cookies to continue)", re.I)

# Rut gon link / trang trung gian. Tach lam hai:
#   HOST    - so khop dung ten mien (khong dung chuoi con, vi "t.co" nam ngay
#             trong "huthamcautienphat.com" -> se bao nham hang loat)
#   PATTERN - so khop trong duong dan + tham so cua href
SHORTENER_HOSTS = (
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd", "cutt.ly",
    "shorturl.at", "rebrand.ly", "s.id", "l.facebook.com", "out.reddit.com",
    "href.li", "lnkd.in", "buff.ly", "db.tt", "qr.ae", "adf.ly",
)
REDIRECT_PATTERNS = (
    "/redirect?", "/goto/", "?url=", "&url=", "/away?", "/link?url=",
    "/url?q=", "?redirect=", "&redirect=", "/out?", "/r.php?",
)

# giu ten cu de code khac khong vo
SHORTENER = SHORTENER_HOSTS + REDIRECT_PATTERNS


def via_redirect(raw_href: str, abs_href: str) -> bool:
    """Link co di qua trang rut gon / chuyen huong trung gian khong."""
    from urllib.parse import urlparse
    host = (urlparse(abs_href or raw_href or "").netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if any(host == h or host.endswith("." + h) for h in SHORTENER_HOSTS):
        return True
    low = (raw_href or "").lower()
    return any(p in low for p in REDIRECT_PATTERNS)


NOFOLLOW_REL = ("nofollow", "ugc", "sponsored")

# ma loi -> (muc nghiem trong, giai thich, viec can lam)
CATALOG = {
    # ---- trang chet han
    "DOMAIN_KHONG_PHAN_GIAI": (SEV_CHET,
        "Ten mien khong phan giai duoc (DNS that bai) - rat co the domain da het han.",
        "Bo link nay khoi danh sach, tim nguon thay the."),
    "KET_NOI_TU_CHOI": (SEV_CHET,
        "May chu tu choi ket noi hoac khong con phuc vu.",
        "Kiem tra lai bang trinh duyet 1 lan; neu van hong thi thay nguon moi."),
    "MANG_CUA_BAN_CHAN": (SEV_GHICHU,
        "MANG DANG CHAY TOOL chan ten mien nay - khong lien quan gi den chat "
        "luong link. Googlebot thu thap tu ha tang cua Google, khong di qua "
        "mang nay, nen gan nhu chac chan van vao duoc binh thuong: may chu van "
        "song (noi duoc toi IP that), chi rieng ket noi tu may nay bi cat.",
        "KHONG phai viec cua ben cung cap, cung KHONG phai loi cua link - dung "
        "thay nguon va dung dua vao yeu cau bu. Day chi la cho tool CHUA DOC "
        "DUOC noi dung: muon biet the <a> con khong thi doi 4G/VPN roi chay "
        "lai tier nay."),
    "SSL_LOI": (SEV_NANG,
        "Chung chi HTTPS het han hoac khong hop le.",
        "Trang van co the con song. Mo bang trinh duyet de xac nhan truoc khi bo."),
    "TIMEOUT": (SEV_NANG,
        "Trang khong phan hoi trong thoi gian cho.",
        "Chay lai rieng link nay voi timeout cao hon truoc khi ket luan."),
    "HTTP_404": (SEV_CHET,
        "Trang tra ve 404 - bai dang da bi xoa han.",
        "Dang lai bai moi tren cung site, hoac thay bang nguon khac."),
    "HTTP_410": (SEV_CHET,
        "Trang tra ve 410 Gone - chu site chu dong xoa vinh vien.",
        "Khong dang lai duoc tren URL cu. Tim nguon khac."),
    "HTTP_403_CHAN_BOT": (SEV_CANHBAO,
        "Bi chan 403 - thuong la tuong lua Cloudflare chan bot chu khong phai mat link.",
        "Bat --js hoac mo tay de xac nhan. Dung voi ket luan la mat link."),
    "HTTP_401": (SEV_CANHBAO,
        "Trang doi dang nhap moi cho xem.",
        "Kiem tra tay bang tai khoan da dung de dang bai."),
    "HTTP_429": (SEV_CANHBAO,
        "Bi gioi han tan suat (429) - ta ban qua nhanh vao domain nay.",
        "Tang per_domain_delay, giam concurrency roi chay lai rieng domain nay."),
    "HTTP_5XX": (SEV_NANG,
        "May chu nguon dang loi (5xx). Thuong la tam thoi.",
        "Chay lai sau vai gio truoc khi ket luan."),
    "KHONG_PHAI_HTML": (SEV_NANG,
        "URL tra ve file khong phai HTML (PDF, anh, JSON...).",
        "Kiem tra lai URL trong file nguon, co the bi dan nham."),
    "SOFT_404": (SEV_CHET,
        "Tra ve 200 nhung noi dung la trang bao loi / bai da bi xoa.",
        "Coi nhu mat link. Dang lai hoac thay nguon."),
    "DOMAIN_RAO_BAN": (SEV_CHET,
        "Domain da het han va dang do trang rao ban / parking.",
        "Bo khoi danh sach. Link nay khong con gia tri va co the doc hai."),
    "CHUYEN_VE_TRANG_CHU": (SEV_CHET,
        "Bi chuyen huong ve trang chu - dau hieu bai viet da bi go.",
        "Dang lai bai. Neu site khong con cho dang, thay nguon."),
    "CHUYEN_SANG_DOMAIN_KHAC": (SEV_NANG,
        "Bi chuyen sang mot ten mien hoan toan khac - site co the da doi chu.",
        "Kiem tra tay xem noi dung con khong."),
    "VONG_LAP_CHUYEN_HUONG": (SEV_CHET,
        "Trang chuyen huong vong tron, khong bao gio mo ra noi dung - ca nguoi "
        "xem lan Googlebot deu khong vao duoc.",
        "Coi nhu MAT LINK. Bao ben cung cap sua trang, hoac thay nguon moi."),

    # ---- Googlebot thay khac nguoi xem
    "GOOGLE_BI_BAO_404": (SEV_CHET,
        "Nguoi mo trang bang trinh duyet van thay binh thuong, nhung khi "
        "Googlebot ghe vao thi trang tra loi 404 'khong ton tai'. Google khong "
        "bao gio thay trang nay nen link khong truyen chut gia tri nao. Day la "
        "kieu giau trang voi rieng Google: Ahrefs, Bing va trinh duyet deu van "
        "thay link.",
        "Coi nhu MAT LINK, doi bu. Bang chung: dan URL vao "
        "search.google.com/test/rich-results - cong cu cua chinh Google tai "
        "trang tu may chu Google va se bao loi 404."),
    "AN_LINK_VOI_GOOGLE": (SEV_CHET,
        "Nguoi mo trang thay the <a> ve he thong cua minh, nhung trang tra cho "
        "Googlebot KHONG co link do (xem cot 'Google thay'). Google chi tinh "
        "nhung gi no nhin thay, nen link khong truyen gia tri.",
        "Coi nhu MAT LINK, doi bu. Bang chung: search.google.com/test/rich-results "
        "-> 'Xem trang da thu thap' -> Ctrl+F ten mien money site: khong co."),
    "CLOAKING_NGUOI_DUNG": (SEV_GHICHU,
        "Googlebot vao trang binh thuong va thay link day du - link VAN TRUYEN "
        "GIA TRI. Nhung nguoi mo bang trinh duyet lai bi chuyen sang trang khac "
        "hoac bao loi (cloaking: Google va nguoi xem thay hai trang khac nhau). "
        "Xem hai cot 'Nguoi xem thay' va 'Google thay'.",
        "Khong phai link hong, KHONG dua vao yeu cau bu. Chi ghi nhan: site "
        "dung cloaking co rui ro bi Google phat ve sau, khong nen dau tu them "
        "vao nguon nay."),

    # ---- trang song nhung khong thay link
    "LINK_BI_GO": (SEV_NANG,
        "Trang con song, doc duoc noi dung that, nhung khong con the <a> nao "
        "tro ve he thong cua minh.",
        "Admin da go link hoac xoa noi dung trong profile. Dang lai hoac thay nguon."),
    "CHUA_RENDER_DUOC": (SEV_CANHBAO,
        "Da mo bang Chromium nhung van khong tai duoc noi dung that "
        "(trang treo, chan bot tan goc, hoac qua cham).",
        "Mo tay bang trinh duyet. KHONG tinh la mat link."),
    "CHUA_CAI_PLAYWRIGHT": (SEV_CANHBAO,
        "Tier nay can render JavaScript nhung may chua cai Playwright nen chua "
        "doc duoc noi dung that. KHONG phai ket luan mat link.",
        "Chay: pip install playwright && playwright install chromium, roi chay lai tier nay."),
    "CAN_BAT_JS": (SEV_CANHBAO,
        "Domain nay render noi dung bang JavaScript, ban chua bat --js.",
        "Chay lai tier nay voi co --js truoc khi ket luan mat link."),
    "TUONG_DANG_NHAP": (SEV_CANHBAO,
        "Noi dung bi che sau tuong dang nhap nen khong doc duoc link.",
        "Kiem tra tay bang tai khoan da dung de dang."),
    "ROBOTS_CHAN_GOOGLE": (SEV_CHET,
        "robots.txt cua site cam Googlebot thu thap dung duong dan nay. Trang "
        "van mo binh thuong voi nguoi, the <a> van con, nhung Google khong bao "
        "gio ghe vao nen link khong truyen duoc chut gia tri nao.",
        "Doi ben cung cap dat link o duong dan khac khong bi cam, hoac bu link "
        "moi. Bang chung: dan nguyen dong Disallow trong robots.txt cua ho."),
    "CAN_DANG_NHAP_MOI_XEM": (SEV_CHET,
        "Da mo bang Chromium that ma trang van doi dang nhap. Khach vang lai "
        "khong xem duoc, nghia la Googlebot cung khong xem duoc - link nay "
        "khong truyen duoc chut gia tri SEO nao.",
        "Dang nhap vao site, doi che do chia se bai sang cong khai roi check lai. "
        "Khong sua duoc thi doi bu nhu link chet."),
    "BI_CHAN_CAPTCHA": (SEV_CANHBAO,
        "Trang tra ve man hinh chong bot (Cloudflare / captcha).",
        "Bat --js, hoac kiem tra tay. Khong tinh la mat link."),
    "TRANG_RONG": (SEV_NANG,
        "Trang tai duoc nhung gan nhu khong co noi dung.",
        "Kiem tra tay - co the bai bi go noi dung nhung URL van song."),

    # ---- link con, nhung chat luong co van de
    "OK": (SEV_TOT,
        "Link song, dofollow, tro dung URL dich.",
        "Khong can lam gi."),
    "NOFOLLOW": (SEV_CANHBAO,
        "The <a> VAN CON nhung mang thuoc tinh nofollow/ugc/sponsored - Google "
        "khong truyen suc manh SEO, nhung link van dua traffic nguoi doc ve.",
        "Van tinh la LINK CON vi con traffic, khong dua vao yeu cau bu. Neu ben "
        "cung cap doi duoc sang dofollow thi tot hon."),
    "SAI_URL_DICH": (SEV_CANHBAO,
        "Link tro dung ten mien nhung sai trang cu the so voi ke hoach.",
        "Kiem tra tay va sua ve dung URL dich neu con quyen chinh sua."),
    "TRO_SAI_TANG": (SEV_CANHBAO,
        "Link VAN CON va van tro ve he thong cua minh, nhung roi vao tang khac "
        "voi khai bao trong config. Xem cot khop_tang de biet no tro vao dau.",
        "Khong phai link hong - khong dua vao yeu cau bu. Hoac sua lai khai bao "
        "tier trong config cho dung thuc te, hoac dat lai link cho dung tang."),
    "TRANG_NOINDEX": (SEV_CHET,
        "The <a> VAN CON tren trang, nhung trang mang the noindex nen Google "
        "khong bao gio doc toi - link khong truyen duoc chut gia tri nao.",
        "Coi nhu MAT LINK: mua backlink la mua gia tri truyen ve, khong phai mua "
        "mot the <a>. Thay bang nguon khac."),
    "CANONICAL_KHAC": (SEV_CHET,
        "Trang co canonical tro sang URL khac, va tool da mo trang canonical do: "
        "KHONG co link ve he thong cua ta. Google chi index ban canonical nen "
        "trang chua link khong len Google - khong truyen gia tri, gan nhu khong "
        "co traffic.",
        "Coi nhu MAT LINK. Doi ben cung cap dat link tren chinh ban canonical "
        "hoac thay nguon. Bang chung: URL canonical ghi o cot Ghi chu."),
    "CANONICAL_CHUA_RO": (SEV_CANHBAO,
        "Trang co canonical tro sang URL khac, nhung tool chua doc duoc trang "
        "canonical (bi chan, loi mang, trang trong) nen chua biet ban canonical "
        "co chua link khong.",
        "Mo URL canonical (cot Ghi chu), Ctrl+F tim money site. Co link thi "
        "link van con, khong co thi coi nhu mat."),
    "CANONICAL_CO_LINK": (SEV_GHICHU,
        "Trang co canonical tro sang URL khac, nhung ban canonical CUNG chua "
        "link ve he thong cua ta - Google gop gia tri ve do, link van tinh.",
        "Khong can lam gi."),
    "ANCHOR_RONG": (SEV_GHICHU,
        "Link ton tai nhung anchor text rong hoac chi la anh.",
        "Khong gap. Neu sua duoc thi dat anchor co tu khoa."),
    "ANCHOR_LA_URL": (SEV_GHICHU,
        "Anchor text la URL tran, gia tri tu khoa gan nhu bang khong.",
        "Khong gap. Sua thanh anchor co nghia neu con quyen chinh sua."),
    "LINK_QUA_TRUNG_GIAN": (SEV_CANHBAO,
        "Link di qua trang chuyen huong / rut gon, khong tro thang ve dich.",
        "Kiem tra xem trung gian co chan bot khong. Uu tien link tro thang."),
    "NHANH_TREN_DA_CHET": (SEV_NANG,
        "Link con va tro dung URL tang tren, nhung chinh URL tang tren do da "
        "CHET (xem cot 'Dich tang tren'). Gia tri tu link nay dung lai o do, "
        "khong chay ve money site.",
        "Khong phai loi cua link nay, khong dua vao yeu cau bu. Sua hoac thay URL "
        "tang tren truoc - no dang keo theo ca nhanh phia duoi."),
    "LINK_BI_AN": (SEV_NANG,
        "The <a> nam trong phan tu bi an (display:none, visibility:hidden, chu co "
        "0...). Nguoi xem khong thay link; Google coi link an la vi pham, "
        "thuong bo qua hoac phat.",
        "Yeu cau ben cung cap dat link hien thi binh thuong. Luu y: link nam "
        "trong tab / accordion dong san cung bi bao the nay - mo trang xem truoc "
        "khi doi."),
    "TRANG_NHIEU_LINK_RA": (SEV_CANHBAO,
        "Trang chua qua nhieu link ra ngoai - dac trung cua trang spam/link farm.",
        "Gia tri truyen ve rat loang. Khong dau tu them vao nguon nay."),
    "KHONG_RO": (SEV_CANHBAO,
        "Khong xac dinh duoc nguyen nhan cu the.",
        "Kiem tra tay."),
}


# =====================================================================
# TANG "KET LUAN" - tra loi cau hoi: link nay co phai mo tay kiem tra khong?
#
# Muc do (1..5) noi ve MUC NGHIEM TRONG. Tang nay noi ve DO TIN CAY cua
# ket luan, la hai chuyen khac nhau:
#
#   SONG       tool doc duoc trang va NHIN THAY the <a>. Chac chan con link.
#              Khong can mo tay. Muc do se noi link do tot hay con khiem khuyet.
#   MAT        tool doc duoc trang va chac chan link khong con (404, 410,
#              domain het han, bai bi go, noindex...). Khong can mo tay,
#              viec can lam la thay nguon moi.
#   CHECK_TAY  tool KHONG doc duoc noi dung that (bi chan bot, captcha, tuong
#              dang nhap, timeout, chua render JS...). Ket luan khong dang tin
#              - dung dem nhung link nay vao so link mat.
#
# CACH_XU_LY cho biet phai lam gi voi nhom CHECK_TAY: co cai chi can chay lai
# tool la xong (may lam), co cai bat buoc mo trinh duyet (nguoi lam).
# =====================================================================

V_SONG, V_MAT, V_CHECK = "SONG", "MAT", "CHECK_TAY"

V_LABEL = {
    V_SONG:  "Link con",
    V_MAT:   "Link mat",
    V_CHECK: "Phai check tay",
}

# Cach xu ly cho nhom CHECK_TAY
X_TOOL, X_NGUOI = "Chay lai tool", "Mo trinh duyet"

VERDICT = {
    # ---------------------------------------------- chac chan con link
    "OK":                   (V_SONG,  ""),
    "ANCHOR_RONG":          (V_SONG,  ""),
    "ANCHOR_LA_URL":        (V_SONG,  ""),
    "SAI_URL_DICH":         (V_SONG,  ""),
    "LINK_QUA_TRUNG_GIAN":  (V_SONG,  ""),
    "TRANG_NHIEU_LINK_RA":  (V_SONG,  ""),
    "TRO_SAI_TANG":         (V_SONG,  ""),
    # Googlebot thay link day du, chi nguoi xem bi dua di cho khac.
    "CLOAKING_NGUOI_DUNG":  (V_SONG,  ""),
    # Link tu no van song. Gia tri mat o tang tren - loi cua URL khac.
    "NHANH_TREN_DA_CHET":   (V_SONG,  ""),
    # Nhan ra bang style inline nen co the nham voi tab/accordion dong san.
    # Chua du chac de tinh la mat.
    "LINK_BI_AN":           (V_SONG,  ""),
    # Google khong truyen suc manh qua nofollow, nhung link van mang traffic
    # nguoi doc ve -> van tinh la con, khong doi bu (ca strict lan loose).
    "NOFOLLOW":             (V_SONG,  ""),
    # Ban canonical cung co link: Google gop gia tri ve do, link van tinh.
    "CANONICAL_CO_LINK":    (V_SONG,  ""),

    # ---------------------------------------------- chac chan mat link
    "DOMAIN_KHONG_PHAN_GIAI": (V_MAT, ""),
    "HTTP_404":             (V_MAT,   ""),
    "HTTP_410":             (V_MAT,   ""),
    "SOFT_404":             (V_MAT,   ""),
    "DOMAIN_RAO_BAN":       (V_MAT,   ""),
    "CHUYEN_VE_TRANG_CHU":  (V_MAT,   ""),
    "LINK_BI_GO":           (V_MAT,   ""),
    # Cac ma duoi day: the <a> VAN CON tren trang, nhung link khong truyen duoc
    # chut gia tri nao ve he thong cua ta. Ve mat SEO khong khac gi mat link,
    # va tool da doc duoc trang nen khong can ai mo tay xac minh -> xep vao MAT
    # va tinh vao khoan doi bu.
    #   TRANG_NOINDEX  Google khong bao gio doc toi trang chua link
    #   CANONICAL_KHAC ban canonical (trang Google index thay) KHONG co link
    #   CAN_DANG_NHAP_MOI_XEM  Googlebot khong co tai khoan nen khong vao duoc
    "TRANG_NOINDEX":        (V_MAT,   ""),
    "CANONICAL_KHAC":       (V_MAT,   ""),
    "CAN_DANG_NHAP_MOI_XEM": (V_MAT,  ""),
    #   ROBOTS_CHAN_GOOGLE     robots.txt cam Googlebot vao dung duong dan nay
    "ROBOTS_CHAN_GOOGLE":   (V_MAT,   ""),
    "VONG_LAP_CHUYEN_HUONG": (V_MAT,  ""),
    # Tool ket luan theo Googlebot: nguoi xem thay link cung vo nghia neu chinh
    # Google bi bao 404 hoac nhan ve trang khong co link.
    "GOOGLE_BI_BAO_404":    (V_MAT,   ""),
    "AN_LINK_VOI_GOOGLE":   (V_MAT,   ""),

    # ---------------------------------------------- chua ket luan duoc
    "CHUA_CAI_PLAYWRIGHT":  (V_CHECK, X_TOOL),
    "CHUA_RENDER_DUOC":     (V_CHECK, X_NGUOI),
    "CAN_BAT_JS":           (V_CHECK, X_TOOL),
    "HTTP_429":             (V_CHECK, X_TOOL),
    "HTTP_5XX":             (V_CHECK, X_TOOL),
    "TIMEOUT":              (V_CHECK, X_TOOL),
    "HTTP_403_CHAN_BOT":    (V_CHECK, X_NGUOI),
    "HTTP_401":             (V_CHECK, X_NGUOI),
    "BI_CHAN_CAPTCHA":      (V_CHECK, X_NGUOI),
    "TUONG_DANG_NHAP":      (V_CHECK, X_NGUOI),
    "CANONICAL_CHUA_RO":    (V_CHECK, X_NGUOI),
    "SSL_LOI":              (V_CHECK, X_NGUOI),
    "KET_NOI_TU_CHOI":      (V_CHECK, X_NGUOI),
    # Loi nam o mang cua nguoi chay tool, khong phai o link. Doi mang roi chay
    # lai la may tu ket luan duoc, nen xep vao nhom X_TOOL.
    "MANG_CUA_BAN_CHAN":    (V_CHECK, X_TOOL),
    "CHUYEN_SANG_DOMAIN_KHAC": (V_CHECK, X_NGUOI),
    "KHONG_PHAI_HTML":      (V_CHECK, X_NGUOI),
    "TRANG_RONG":           (V_CHECK, X_NGUOI),
    "KHONG_RO":             (V_CHECK, X_NGUOI),
}

# Cau huong dan ngan gon cho tung ma trong nhom CHECK_TAY. Hien o sheet
# "Can check tay" de nguoi dung khong phai doan phai lam gi.
HUONG_DAN_CHECK = {
    "CHUA_CAI_PLAYWRIGHT": "Cai Playwright roi chay lai tier nay: "
                           "pip install playwright && playwright install chromium",
    "CAN_BAT_JS":          "Chay lai tier nay voi co --js",
    "HTTP_429":            "Tang per_domain_delay, giam concurrency, chay lai rieng domain nay",
    "HTTP_5XX":            "May chu nguon dang loi. Chay lai sau vai gio",
    "TIMEOUT":             "Chay lai voi timeout cao hon. Van timeout thi mo tay",
    "HTTP_403_CHAN_BOT":   "Mo URL bang trinh duyet, Ctrl+F tim ten mien money site",
    "HTTP_401":            "Dang nhap bang tai khoan da dung de dang bai roi tim link",
    "BI_CHAN_CAPTCHA":     "Mo URL bang trinh duyet, qua captcha roi Ctrl+F tim link",
    "TUONG_DANG_NHAP":     "Dang nhap vao site roi kiem tra link con trong bai khong",
    "CANONICAL_CHUA_RO":   "Mo URL canonical (cot Ghi chu), Ctrl+F tim ten mien money site",
    "SSL_LOI":             "Mo bang trinh duyet, bo qua canh bao chung chi de xem trang",
    "KET_NOI_TU_CHOI":     "Mo bang trinh duyet 1 lan. Van hong thi coi nhu mat link",
    "MANG_CUA_BAN_CHAN":   "Khong phai loi cua link. Chi can doc noi dung thi doi "
                           "4G/VPN roi chay lai tier nay",
    "CHUYEN_SANG_DOMAIN_KHAC": "Mo URL cuoi xem noi dung bai cu con khong",
    "KHONG_PHAI_HTML":     "Doi chieu lai URL trong file nguon, co the dan nham",
    "CHUA_RENDER_DUOC":    "Da mo bang Chromium ma van khong tai duoc. Mo tay bang "
                           "trinh duyet, doi trang nap xong roi Ctrl+F tim money site",
    "TRANG_RONG":          "Mo URL xem bai con noi dung khong hay chi con vo trang",
    "KHONG_RO":            "Mo URL bang trinh duyet, Ctrl+F tim ten mien money site",
}


def verdict_of(code):
    """code -> (ket_luan, cach_xu_ly, huong_dan). Ma la -> coi nhu phai check tay."""
    v, how = VERDICT.get(code, (V_CHECK, X_NGUOI))
    return v, how, HUONG_DAN_CHECK.get(code, "")


def dem_ket_luan(results):
    """Dem so link theo ket luan. Tra ve dict de dung chung cho console/xlsx."""
    d = {V_SONG: 0, V_MAT: 0, V_CHECK: 0, "TONG": 0, "HOAN_HAO": 0,
         X_TOOL: 0, X_NGUOI: 0}
    for r in results:
        v = getattr(r, "ket_luan", "") or V_CHECK
        d["TONG"] += 1
        d[v] = d.get(v, 0) + 1
        if v == V_SONG and str(getattr(r, "severity", "")) == str(SEV_TOT):
            d["HOAN_HAO"] += 1
        if v == V_CHECK:
            how = getattr(r, "cach_xu_ly", "") or X_NGUOI
            d[how] = d.get(how, 0) + 1
    return d


def diagnose(res, page, cfg_js_forced=False, outbound_limit=150, loose=False):
    """Tra ve (ma_loi, muc_nghiem_trong, giai_thich, viec_can_lam).

    res   : doi tuong Result da duoc checker dien
    page  : dict tin hieu tho tu trang (title, text_len, outbound, html_snippet...)
    loose : che do long (config 'mode: loose') - vao duoc trang, thay the <a>
            ve dich la song. noindex / nofollow / canonical / robots.txt khong
            con lam link thanh "Link mat"; cot rel, indexable, note van ghi lai.
    """
    page = page or {}
    title = page.get("title", "") or ""
    snippet = page.get("snippet", "") or ""
    blob = (title + " " + snippet)[:6000]
    err = (page.get("error") or "").lower()
    code = 0
    try:
        code = int(res.http_code)
    except (TypeError, ValueError):
        code = 0

    # ---------------------------------------------------------- robots.txt cam
    # Dat TRUOC moi nhanh khac vi day la bang chung DOC LAP voi viec tool co doc
    # duoc noi dung hay khong. Trang tra 403 vi Cloudflare chan ta, ma robots.txt
    # lai cam luon Googlebot -> khong con gi phai check tay: Google cung khong
    # vao duoc, ket luan da chac. Nhung dong 404/410/DNS hong khong bi anh huong
    # vi checker bo qua han buoc doc robots.txt cho chung (cot robots de rong).
    if getattr(res, "robots", "") == "bi chan" and not loose:
        return _pack("ROBOTS_CHAN_GOOGLE", res)

    # ---------------------------------------------------------- trang loi
    if res.status == "PAGE_ERROR":
        # Dat truoc SSL/timeout/connect: khi mang chan theo ten mien, loi bao ve
        # co the la reset, timeout hay loi TLS tuy cach chan - nhung nguyen nhan
        # thi da biet chac roi, khong can doan tu thong bao loi.
        if page.get("mang_chan"):
            key = "MANG_CUA_BAN_CHAN"
        elif page.get("vong_lap") and "redirect" in err:
            # Ca httpx lan Chromium (neu da thu) deu bao chuyen huong vong tron.
            key = "VONG_LAP_CHUYEN_HUONG"
        elif "ssl" in err or "certificate" in err:
            key = "SSL_LOI"
        elif "timeout" in err or "timedout" in err:
            key = "TIMEOUT"
        elif "getaddrinfo" in err or "name or service" in err or "nodename" in err \
                or "dns" in err:
            key = "DOMAIN_KHONG_PHAN_GIAI"
        elif "connect" in err or "refused" in err or "reset" in err or "unreachable" in err:
            key = "KET_NOI_TU_CHOI"
        elif code == 404:
            key = "HTTP_404"
        elif code == 410:
            key = "HTTP_410"
        elif code == 403:
            key = "BI_CHAN_CAPTCHA" if CAPTCHA_PAT.search(blob) else "HTTP_403_CHAN_BOT"
        elif code == 401:
            key = "HTTP_401"
        elif code == 429:
            key = "HTTP_429"
        elif 500 <= code <= 599:
            key = "HTTP_5XX"
        elif "html" in err or "content-type" in err or page.get("not_html"):
            key = "KHONG_PHAI_HTML"
        else:
            key = "KHONG_RO"
        return _pack(key, res)

    # ---------------------------------------------------------- trang 200 nhung hong
    if PARKED_PAT.search(blob):
        return _pack("DOMAIN_RAO_BAN", res)
    if SOFT_404_PAT.search(title):
        return _pack("SOFT_404", res)
    if page.get("redirected_off_domain"):
        return _pack("CHUYEN_SANG_DOMAIN_KHAC", res)
    if page.get("redirected_to_home"):
        return _pack("CHUYEN_VE_TRANG_CHU", res)

    # ---------------------------------------------------------- khong thay link
    if res.status == "NOT_FOUND":
        if CAPTCHA_PAT.search(blob):
            return _pack("BI_CHAN_CAPTCHA", res)
        if LOGIN_PAT.search(blob):
            # Luot HTTP tho gap tuong dang nhap thi chua chac - nhieu site tra
            # khung dang nhap cho client la roi moi ve noi dung that bang JS.
            # Nhung da mo bang Chromium that ma van bi chan thi khong con nghi
            # ngo gi: khach vang lai khong xem duoc, Googlebot cung vay.
            # Che do long chi hoi "co vao duoc khong": khong vao duoc thi
            # de nguoi check tay, khong ket luan mat link.
            if res.rendered == "playwright" and not loose:
                return _pack("CAN_DANG_NHAP_MOI_XEM", res)
            return _pack("TUONG_DANG_NHAP", res)
        if page.get("js_unavailable"):
            return _pack("CHUA_CAI_PLAYWRIGHT", res)
        if page.get("render_that_bai"):
            return _pack("CHUA_RENDER_DUOC", res)
        if cfg_js_forced and res.rendered != "playwright":
            return _pack("CAN_BAT_JS", res)
        if (page.get("text_len", 9999) < 1500
                and SOFT_404_THAN_PAT.search(page.get("snippet") or "")):
            return _pack("SOFT_404", res)
        if page.get("text_len", 9999) < 400:
            return _pack("TRANG_RONG", res)
        return _pack("LINK_BI_GO", res)

    # ---------------------------------------------------------- link con song
    canonical_khac = res.indexable == "no" and "canonical" in (res.note or "").lower()
    if res.indexable == "no" and not canonical_khac and not loose:
        return _pack("TRANG_NOINDEX", res)
    # Canonical khac: ket luan theo BAN CANONICAL - trang Google index thay cho
    # trang nay. checker.py mo trang do va ghi ket qua vao page["canon_kq"].
    # Ban canonical co link -> gia tri gop ve do, xet tiep nhu link binh thuong.
    if canonical_khac and not loose:
        ckq = page.get("canon_kq") or {}
        if ckq.get("found") is False:
            return _pack("CANONICAL_KHAC", res)
        if not ckq.get("found"):
            return _pack("CANONICAL_CHUA_RO", res)
    # Che do long: link song thi khong doi bu, TRU link tro sai tang. doisoat.py
    # dem khoan "sai tang" theo ma loi CHINH, nen o day sai tang phai thang
    # SAI_URL_DICH / LINK_QUA_TRUNG_GIAN - hai ma do van nam o canh_bao_them.
    if loose and page.get("sai_tang"):
        return _pack("TRO_SAI_TANG", res)
    if page.get("via_redirect"):
        return _pack("LINK_QUA_TRUNG_GIAN", res)
    if "khong khop URL" in (res.note or "") or page.get("domain_only_match"):
        return _pack("SAI_URL_DICH", res)
    # Link con, tro dung he thong cua minh, nhung khong phai tang da khai bao.
    # Day la sai lech giua so do tren giay va thuc te, khong phai link hong.
    if page.get("sai_tang"):
        return _pack("TRO_SAI_TANG", res)
    # Hai ma duoi dat SAU TRO_SAI_TANG du muc nang hon: doisoat.py dem khoan
    # "sai tang" theo ma loi CHINH, day len truoc thi so bu bi hut di.
    if page.get("nhanh_tren_chet"):
        return _pack("NHANH_TREN_DA_CHET", res)
    if page.get("link_bi_an"):
        return _pack("LINK_BI_AN", res)
    # nofollow van la Link con (con traffic), nen dat SAU cac ma song khac:
    # dung truoc thi hut mat TRO_SAI_TANG - khoan duy nhat cua link song con
    # tinh vao yeu cau bu.
    rel = (res.rel or "").lower()
    if any(r in rel for r in NOFOLLOW_REL) and not loose:
        return _pack("NOFOLLOW", res)
    if canonical_khac and not loose:
        return _pack("CANONICAL_CO_LINK", res)
    if page.get("outbound", 0) > outbound_limit:
        return _pack("TRANG_NHIEU_LINK_RA", res)
    a = (res.anchor_text or "").strip()
    if not a or a == "(anh / rong)":
        return _pack("ANCHOR_RONG", res)
    if a.lower().startswith(("http://", "https://", "www.")):
        return _pack("ANCHOR_LA_URL", res)
    return _pack("OK", res)


def _pack(key, res):
    sev, why, todo = CATALOG[key]
    return key, sev, why, todo


# Ma loi noi ve MOI TRUONG CHAY TOOL, khong noi gi ve chat luong link. Tier
# nao khong lam chung nghiem trong hon hay nhe di, nen chung dung ngoai
# bump_by_tier. Neu khong, mot link tier 2 (priority 1) ma tool khong doc duoc
# vi mang nha bi day len muc NANG mau cam - trong nhu link dang hong, trong khi
# thuc te chua do duoc gi ve no.
MA_MOI_TRUONG = ("MANG_CUA_BAN_CHAN",)


def bump_by_tier(sev: int, tier, tier_priority: dict, code: str = "") -> int:
    """Tier cang cao trong kim tu thap thi cung mot loi cang nghiem trong.

    tier_priority: {so_tier: do_uu_tien}. Tier co priority = 1 duoc nang muc len
    mot bac; tier co priority >= 4 duoc ha mot bac (chi theo doi tong quan).

    Rieng cac ma trong MA_MOI_TRUONG giu nguyen muc: chung mo ta may chay tool,
    khong mo ta link.
    """
    if code in MA_MOI_TRUONG:
        return sev
    try:
        p = int(tier_priority.get(int(tier), int(tier)))
    except (TypeError, ValueError):
        return sev
    if sev >= SEV_TOT:
        return sev
    if p <= 1:
        return max(SEV_CHET, sev - 1)
    if p >= 4:
        return min(SEV_GHICHU, sev + 1)
    return sev


def cap_theo_ket_luan(sev, ket_luan):
    """Khong duoc gan muc CHET cho mot dong ma tool CHUA ket luan duoc.

    Muc do va ket luan la hai tang khac nhau, nhung de trong bao cao mot dong
    vua ghi "Phai check tay" vua to do dam "CHET" thi nguoi doc hieu nham la
    link da mat. Nhom chua ket luan duoc cao nhat chi den NANG.
    """
    if ket_luan == V_CHECK:
        return max(SEV_NANG, sev)
    return sev


# ----------------------------------------------------------------- canh bao phu
# Mot link co the vua nofollow vua tro sai URL. Ma loi chinh chi lay cai nang nhat,
# nen liet ke phan con lai o cot rieng de khong bo sot khi kiem tra tay.
def secondary(res, page, primary="", loose=False):
    """Che do long bo qua nofollow / noindex / canonical: khong ghi vao day, vi
    doisoat.py doc cot canh_bao_them de tinh khoan "khong truyen gia tri"."""
    page = page or {}
    if res.status != "FOUND":
        return []
    out = []
    rel = (res.rel or "").lower()
    if any(r in rel for r in NOFOLLOW_REL) and not loose:
        out.append("NOFOLLOW")
    if res.indexable == "no" and not loose:
        if "canonical" not in (res.note or "").lower():
            out.append("TRANG_NOINDEX")
        else:
            found = (page.get("canon_kq") or {}).get("found")
            out.append("CANONICAL_CO_LINK" if found else
                       "CANONICAL_KHAC" if found is False else "CANONICAL_CHUA_RO")
    if page.get("domain_only_match") or "sai URL dich" in (res.note or ""):
        out.append("SAI_URL_DICH")
    if page.get("sai_tang"):
        out.append("TRO_SAI_TANG")
    if page.get("nhanh_tren_chet"):
        out.append("NHANH_TREN_DA_CHET")
    if page.get("link_bi_an"):
        out.append("LINK_BI_AN")
    if page.get("via_redirect"):
        out.append("LINK_QUA_TRUNG_GIAN")
    if page.get("outbound", 0) > 150:
        out.append("TRANG_NHIEU_LINK_RA")
    a = (res.anchor_text or "").strip()
    if not a or a == "(anh / rong)":
        out.append("ANCHOR_RONG")
    elif a.lower().startswith(("http://", "https://", "www.")):
        out.append("ANCHOR_LA_URL")
    return [c for c in out if c != primary]


# =====================================================================
# GOOGLEBOT LA CHUAN
#
# Tool tra loi "link co truyen gia tri SEO khong", ma Google chi truyen gia tri
# qua nhung gi Googlebot nhin thay. Nen ngoai luot doc bang trinh duyet (goc
# nhin NGUOI XEM), moi URL con duoc tai lai voi User-Agent Googlebot, va ket
# luan cuoi cung di theo Googlebot:
#
#   Nguoi xem        Googlebot          Ket luan
#   thay link        thay link          theo trang Googlebot nhan (OK/nofollow...)
#   thay link        bi bao 404         GOOGLE_BI_BAO_404   - Link mat
#   thay link        khong thay link    AN_LINK_VOI_GOOGLE  - Link mat
#   bi chuyen di/404 thay link          CLOAKING_NGUOI_DUNG - Link con, ghi chu
#   bi chan captcha  thay link          theo trang Googlebot nhan - Link con
#   bat ky           bi chan 403/429    giu ket luan cua nguoi xem
#
# Bat doi xung co chu dich: Googlebot NHAN DUOC noi dung thi tin tuyet doi (may
# chu that khong bao gio cho Googlebot gia xem nhieu hon Googlebot that). Con
# Googlebot BI CHAN bang 403/429/captcha thi KHONG tin: nhieu site kiem tra IP
# va chi chan Googlebot gia - Googlebot that van vao duoc. Rieng 404/410 thi
# tin: chan bot gia tra 403, khong ai tra "trang khong ton tai".
# =====================================================================

G_THAY, G_404, G_AN, G_CHUYEN, G_CHAN = "thay", "404", "an", "chuyen", "chan"

# Ma cua goc nhin nguoi xem cho biet ho duoc dua toi mot trang KHAC (khong phai
# chi bi chan). Googlebot van thay link thi day moi dung la cloaking.
MA_NGUOI_XEM_KHAC = ("LINK_BI_GO", "CHUYEN_VE_TRANG_CHU", "CHUYEN_SANG_DOMAIN_KHAC",
                     "SOFT_404", "HTTP_404", "HTTP_410", "DOMAIN_RAO_BAN",
                     "VONG_LAP_CHUYEN_HUONG")


def goc_nhin_google(page):
    """Phan loai trang Googlebot nhan duoc. None = chua hoi Googlebot."""
    gb = (page or {}).get("gb")
    if not gb:
        return None
    if gb.get("loi"):
        return G_CHAN
    code = gb.get("http") or 0
    if code in (404, 410):
        return G_404
    if not 200 <= code < 300 or not gb.get("html"):
        return G_CHAN
    sig = gb.get("sig") or {}
    blob = ((sig.get("title") or "") + " " + (sig.get("snippet") or ""))[:6000]
    if CAPTCHA_PAT.search(blob) or LOGIN_PAT.search(blob):
        return G_CHAN
    if gb.get("found"):
        return G_THAY
    if SOFT_404_PAT.search(sig.get("title") or "") or PARKED_PAT.search(blob):
        return G_404
    if sig.get("redirected_off_domain") or sig.get("redirected_to_home"):
        return G_CHUYEN
    if sig.get("text_len", 0) < 400:
        # Trang rong: co the la khung cho JavaScript ve noi dung. Google co
        # render JS, HTML tho khong noi len duoc gi.
        return G_CHAN
    return G_AN


def _rut_gon(url, n=48):
    from urllib.parse import urlparse
    u = urlparse(url or "")
    s = (u.netloc + (u.path if u.path not in ("", "/") else "/")) or (url or "")
    return s if len(s) <= n else s[:n - 3] + "..."


NHAN_NGUOI_XEM = {
    "HTTP_404": "trang bao 404",
    "HTTP_410": "trang bao 410 (da xoa)",
    "SOFT_404": "trang bao khong ton tai",
    "DOMAIN_RAO_BAN": "domain dang rao ban",
    "VONG_LAP_CHUYEN_HUONG": "chuyen huong vong tron",
    "BI_CHAN_CAPTCHA": "bi chan captcha",
    "HTTP_403_CHAN_BOT": "bi chan (HTTP 403)",
    "HTTP_401": "doi dang nhap (HTTP 401)",
    "HTTP_429": "bi gioi han toc do (HTTP 429)",
    "HTTP_5XX": "may chu dang loi (5xx)",
    "TUONG_DANG_NHAP": "doi dang nhap",
    "CAN_DANG_NHAP_MOI_XEM": "doi dang nhap",
    "DOMAIN_KHONG_PHAN_GIAI": "ten mien khong ton tai",
    "KET_NOI_TU_CHOI": "khong ket noi duoc",
    "TIMEOUT": "khong phan hoi (timeout)",
    "SSL_LOI": "loi chung chi SSL",
    "MANG_CUA_BAN_CHAN": "mang may chay tool chan",
    "KHONG_PHAI_HTML": "khong phai trang web",
    "CHUA_RENDER_DUOC": "chua doc duoc noi dung",
    "CHUA_CAI_PLAYWRIGHT": "chua doc duoc noi dung",
    "CAN_BAT_JS": "chua doc duoc noi dung",
    "TRANG_RONG": "trang trong",
    "KHONG_RO": "khong doc duoc",
}


def nhan_nguoi_xem(res, page, key):
    """Nguoi mo trang bang trinh duyet thay gi - mot cum tu ngan."""
    if page.get("redirected_off_domain") or page.get("redirected_to_home"):
        return "bi chuyen sang " + _rut_gon(res.final_url)
    if res.status == "FOUND":
        return "thay link"
    if key in NHAN_NGUOI_XEM:
        return NHAN_NGUOI_XEM[key]
    if res.status == "NOT_FOUND":
        return "khong thay link"
    if res.http_code:
        return "trang loi HTTP %s" % res.http_code
    return "khong vao duoc trang"


def nhan_googlebot(res, page, g):
    """Googlebot thay gi - mot cum tu ngan."""
    if getattr(res, "robots", "") == "bi chan":
        return "bi robots.txt cam vao"
    gb = page.get("gb") or {}
    if g is None:
        ly_do = page.get("gb_bo_qua")
        return "chua hoi - %s" % ly_do if ly_do else "chua hoi"
    if g == G_THAY:
        phu = []
        if any(r in (gb.get("rel") or "").lower() for r in NOFOLLOW_REL):
            phu.append("nofollow")
        if gb.get("indexable") == "no":
            phu.append("canonical khac" if "canonical" in (gb.get("note") or "")
                       else "noindex")
        return "thay link" + (" (%s)" % ", ".join(phu) if phu else "")
    if g == G_404:
        code = gb.get("http")
        return "bi bao %s" % code if code in (404, 410) else "bi bao khong ton tai"
    if g == G_CHUYEN:
        return "bi chuyen sang " + _rut_gon(gb.get("final_url"))
    if g == G_AN:
        if gb.get("desktop_found"):
            return "khong thay link (ban dien thoai)"
        return "khong thay link"
    if gb.get("loi"):
        return "khong ro - %s" % gb["loi"]
    code = gb.get("http") or 0
    if code and not 200 <= code < 300:
        return "khong ro - bi chan HTTP %s" % code
    if code and not gb.get("html"):
        return "khong ro - khong phai trang web"
    sig = gb.get("sig") or {}
    blob = ((sig.get("title") or "") + " " + (sig.get("snippet") or ""))[:6000]
    if CAPTCHA_PAT.search(blob) or LOGIN_PAT.search(blob):
        return "khong ro - trang chan bot / doi dang nhap"
    return "khong ro - trang gan nhu trong"


def _ban_google(res, gb):
    """Doi tuong co cung cac truong ma diagnose() doc, lay tu trang Googlebot."""
    from types import SimpleNamespace
    return SimpleNamespace(
        status="FOUND", http_code=str(gb.get("http") or ""), rendered="http",
        robots=getattr(res, "robots", ""), tier=res.tier, source_url=res.source_url,
        final_url=gb.get("final_url", ""), rel=gb.get("rel", ""),
        indexable=gb.get("indexable", ""), note=gb.get("note", ""),
        anchor_text=gb.get("anchor_text", ""), points_to=gb.get("points_to", ""),
        khop_tang=gb.get("khop_tang", ""))


def phan_xu(res, page, cfg_js_forced=False, outbound_limit=150, loose=False):
    """Ket luan cuoi cung cho mot dong, lay Googlebot lam chuan.

    Tra ve dict:
        code       ma loi chinh
        view       "google" neu ket luan dua tren trang Googlebot nhan duoc
        sig        tin hieu trang dung de liet ke canh bao phu
        them       ma phu bo sung (vd CLOAKING_NGUOI_DUNG)
        nguoi_xem  / googlebot   hai cum tu cho hai cot de doc
    """
    page = page or {}
    key = diagnose(res, page, cfg_js_forced, outbound_limit, loose)[0]
    # Che do long khong lay Googlebot lam chuan, du page co san du lieu 'gb'.
    g = None if loose else goc_nhin_google(page)
    out = {"code": key, "view": None, "sig": page, "them": [],
           "nguoi_xem": nhan_nguoi_xem(res, page, key),
           "googlebot": nhan_googlebot(res, page, g)}
    if g in (None, G_CHAN):
        return out

    gb = page["gb"]
    nguoi_thay = res.status == "FOUND" and not (
        page.get("redirected_off_domain") or page.get("redirected_to_home"))

    if g == G_THAY:
        sig = dict(gb.get("sig") or {})
        for k in ("nhanh_tren_chet", "canon_kq"):
            if page.get(k):
                sig[k] = page[k]
        key_google = diagnose(_ban_google(res, gb), sig, False, outbound_limit,
                              loose)[0]
        out.update(view="google", sig=sig, code=key_google)
        if not nguoi_thay and key in MA_NGUOI_XEM_KHAC:
            if key_google == "OK":
                out["code"] = "CLOAKING_NGUOI_DUNG"
            else:
                out["them"].append("CLOAKING_NGUOI_DUNG")
        return out

    if g == G_404:
        # Nguoi xem cung bi 404 thi giu ma HTTP_404 - khong co gi la che giau.
        if res.http_code not in ("404", "410"):
            out["code"] = "GOOGLE_BI_BAO_404"
        return out

    # G_AN / G_CHUYEN: Googlebot nhan trang that nhung khong co link.
    if nguoi_thay:
        if res.rendered == "playwright":
            # Link do JavaScript chen vao sau: HTML tho gui cho Googlebot khong
            # co la binh thuong, Google render JS roi moi doc. Khong ket luan.
            out["googlebot"] = "khong ro - link chen bang JavaScript"
        else:
            out["code"] = "AN_LINK_VOI_GOOGLE"
    return out


# ------------------------------------------------------------------ yeu cau
# Tach "phai thay link moi" voi "chi can sua link cu": mot bai 404 thi bat
# buoc dang lai, con link nofollow / tro sai dich thi ben cung cap sua tren
# chinh bai do la xong - re hon va nhanh hon nhieu.
YC_THAY, YC_SUA, YC_TANG_TREN = "Thay link moi", "Sua link", "Sua tang tren"
LOAI_YEU_CAU = {
    "CAN_DANG_NHAP_MOI_XEM": YC_SUA,
    "TRO_SAI_TANG":          YC_SUA,
    "SAI_URL_DICH":          YC_SUA,
    "LINK_BI_AN":            YC_SUA,
    "NHANH_TREN_DA_CHET":    YC_TANG_TREN,
}


def yeu_cau(code, ket_luan):
    if code in LOAI_YEU_CAU:
        return LOAI_YEU_CAU[code]
    return YC_THAY if ket_luan == V_MAT else ""
