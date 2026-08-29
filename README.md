# Backlink Checker

Kiem tra tinh trang backlink cho mo hinh kim tu thap nhieu tang.
Doc `CLAUDE.md` de hieu cau hinh, bang ma loi va flow chay chuan.

## Cai dat lan dau

Yeu cau: Python 3.10 tro len.

### Windows (PowerShell trong VS Code)

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

Neu PowerShell bao loi khong chay duoc script, chay lenh nay mot lan:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Dan link Google Sheet o dau

Mo `config/checkbacklink.yaml`, tim muc `source:` gan dau file, dan link vao
dong `url:`. Nho share file do o che do "Anyone with the link - Viewer".

```yaml
source:
  type: auto
  url: "https://docs.google.com/spreadsheets/d/1AbC...XyZ/edit"
```

## Dung cho mot du an moi

```bash
cp config/_mau.yaml config/tensite.yaml
```

Sua trong `config/tensite.yaml`: `money_domain`, `target_urls`, link Google
Sheets o `source.url`, va tu khoa `match` cua tung tier cho khop ten tab.

## Chay

Mot lenh duy nhat lam het moi viec:

```powershell
.\blcheck.bat run
```

Phai co `.\` o dau — PowerShell khong tim lenh trong thu muc hien tai.

Nap du lieu tu Google Sheet, lam sach, check tung tier theo thu tu uu tien,
xuat CSV + XLSX to mau, so sanh voi lan chay truoc, in bao cao.

Trong CMD thi go `blcheck run`, Git Bash thi `./blcheck run`, hoac goi thang
`python src/cli.py run` o bat ky dau.

Go `.\blcheck.bat` khong kem lenh -> vao che do tuong tac.

### Lan chay dau

```powershell
.\blcheck.bat ingest --dry-run   # xem tab nao vao tier nao
.\blcheck.bat run -n 20          # thu 20 link moi tier
.\blcheck.bat run                # chay that
```

### Cac lenh con

```powershell
.\blcheck.bat run -t 1           # chi mot tier
.\blcheck.bat run --skip-ingest  # dung master CSV co san
.\blcheck.bat check -t 2         # chi check, khong tai lai Sheet
.\blcheck.bat diff <cu>.csv <moi>.csv -o results/thay-doi.csv
.\blcheck.bat --help
```

Ket qua ra `results/<ngay>_<site>_tier<N>.csv` va `.xlsx` (da to mau theo muc do
nghiem trong, kem cot chan doan va viec can lam).

## Tham so dong lenh

| Co | Y nghia |
|----|---------|
| `-c <file>` | File cau hinh YAML, mac dinh `config/checkbacklink.yaml` |
| `-t N` | Chi chay mot tier |
| `-n N` | Chi check N link dau moi tier, de thu |
| `--skip-ingest` | Dung master CSV co san, khong tai lai Google Sheet |
| `--js` / `--no-js` | Ep bat / tat render JavaScript |
| `--no-diff` | Bo qua buoc so sanh voi lan truoc |

Moi tham so con lai (concurrency, delay, timeout, domain can render JS...) nam
trong file YAML, khong phai o dong lenh.

## Yeu cau voi Google Sheets / Docs

File phai duoc chia se o che do **Anyone with the link - Viewer**. Neu khong,
script bao loi 403 kem huong dan.
