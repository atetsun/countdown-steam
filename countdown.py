"""
Countdown event Steam (Sale / Fest) di Discord lewat webhook, ala SteamDB.

Satu pesan embed di channel di-EDIT terus (bukan kirim baru), jadi channel tidak penuh.
Status berubah otomatis mengikuti tanggal di events.json:
  sebelum event  -> "Mulai dalam X hari"
  saat event     -> "SEDANG BERLANGSUNG" + sisa waktu + progress bar
  setelah event  -> pindah ke sale berikutnya (Winter -> Spring -> Summer -> ...)

  python countdown.py                       kirim / edit pesan sekali (dipakai GitHub Actions)
  python countdown.py --lihat               tampilkan isi embed tanpa mengirim
  python countdown.py --lihat --sekarang 2026-12-20T12:00    simulasi waktu (UTC)

Webhook dibaca dari variabel lingkungan DISCORD_WEBHOOK_COUNTDOWN (GitHub Secrets),
atau dari countdown_webhook.txt kalau dijalankan di laptop.
"""
import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.abspath(__file__))
EVENTS_FILE = os.path.join(BASE, "events.json")
STATE_FILE = os.path.join(BASE, "countdown_state.json")
WEBHOOK_FILE = os.path.join(BASE, "countdown_webhook.txt")

# Steam memulai dan mengakhiri event jam 10:00 waktu Pacific (otomatis menyesuaikan jam musim panas)
ZONA = "America/Los_Angeles"
JAM = "10:00"

# Halaman countdown live (beranimasi). Kosongkan "" kalau tidak mau ada tautan.
HALAMAN_URL = "https://atetsun.github.io/countdown-live/"

USERNAME = "Steam Countdown"
MAKS_MENDATANG = 4  # berapa event mendatang yang ditampilkan di bawah headline
WARNA_LIVE = 0x57F287
WARNA_MENDATANG = 0x5865F2
WARNA_KOSONG = 0x99AAB5
UA = "Mozilla/5.0 (compatible; SteamCountdownBot/1.0)"


def http_json(url, data=None, method=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8") if data is not None else None,
        headers={"User-Agent": UA, "Content-Type": "application/json"},
        method=method or ("POST" if data is not None else "GET"),
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8")
        return json.loads(body) if body.strip() else None


def ke_utc(tanggal, jam=JAM, zona=ZONA):
    d = datetime.strptime(f"{tanggal} {jam}", "%Y-%m-%d %H:%M")
    return d.replace(tzinfo=ZoneInfo(zona)).astimezone(timezone.utc)


def muat_event():
    data = json.load(open(EVENTS_FILE, encoding="utf-8"))
    hasil = []
    for e in data:
        try:
            e["_s"] = ke_utc(e["mulai"], e.get("jam", JAM), e.get("zona", ZONA))
            e["_e"] = ke_utc(e["selesai"], e.get("jam", JAM), e.get("zona", ZONA))
            if e["_e"] <= e["_s"]:
                raise ValueError("tanggal selesai harus setelah tanggal mulai")
            hasil.append(e)
        except Exception as ex:
            print(f"  event dilewati ({e.get('nama', '?')}): {ex}")
    return sorted(hasil, key=lambda x: x["_s"])


def ts(dt):
    return int(dt.timestamp())


def sisa_teks(detik):
    detik = max(0, int(detik))
    h, sisa = divmod(detik, 86400)
    j, sisa = divmod(sisa, 3600)
    m = sisa // 60
    if h:
        return f"{h} hari {j} jam"
    if j:
        return f"{j} jam {m} menit"
    return f"{m} menit"


def bar(e, now, panjang=12):
    total = (e["_e"] - e["_s"]).total_seconds()
    jalan = min(max((now - e["_s"]).total_seconds(), 0), total)
    persen = jalan / total
    isi = round(persen * panjang)
    return f"{'█' * isi}{'░' * (panjang - isi)} {int(persen * 100)}%"


def tag_perkiraan(e):
    return " *(perkiraan)*" if e.get("perkiraan") else ""


def buat_payload(events, now):
    live = [e for e in events if e["_s"] <= now < e["_e"]]
    mendatang = [e for e in events if e["_s"] > now]
    sale_live = next((e for e in live if e.get("jenis") == "sale"), None)
    sale_next = next((e for e in mendatang if e.get("jenis") == "sale"), None)
    utama = sale_live or sale_next

    if sale_live:
        e = sale_live
        judul = f"{e.get('emoji', '🔥')} {e['nama']}"
        warna = WARNA_LIVE
        deskripsi = (
            f"🟢 **SEDANG BERLANGSUNG**\n"
            f"```\n{sisa_teks((e['_e'] - now).total_seconds())} lagi\n```"
            f"Berakhir <t:{ts(e['_e'])}:R> • <t:{ts(e['_e'])}:F>\n"
            f"`{bar(e, now)}`"
        )
    elif sale_next:
        e = sale_next
        judul = f"{e.get('emoji', '🛒')} {e['nama']}"
        warna = WARNA_MENDATANG
        deskripsi = (
            f"⏳ **Mulai dalam**\n"
            f"```\n{sisa_teks((e['_s'] - now).total_seconds())}\n```"
            f"<t:{ts(e['_s'])}:R> • <t:{ts(e['_s'])}:F>{tag_perkiraan(e)}"
        )
    else:
        e = None
        judul, warna = "🎮 Steam Countdown", WARNA_KOSONG
        deskripsi = "Jadwal sale Steam berikutnya belum diumumkan."

    fields = []
    for x in live:
        if x is utama:
            continue
        fields.append({
            "name": f"{x.get('emoji', '🟢')} {x['nama']} • LIVE",
            "value": f"Berakhir <t:{ts(x['_e'])}:R>\n`{bar(x, now)}`",
            "inline": False,
        })
    for x in [m for m in mendatang if m is not utama][:MAKS_MENDATANG]:
        fields.append({
            "name": f"{x.get('emoji', '📅')} {x['nama']}",
            "value": f"Mulai <t:{ts(x['_s'])}:R> • <t:{ts(x['_s'])}:D>{tag_perkiraan(x)}",
            "inline": False,
        })

    embed = {
        "title": judul,
        "description": deskripsi,
        "color": warna,
        "fields": fields,
        "footer": {"text": "Diperbarui otomatis • waktu mengikuti zona waktumu"},
        "timestamp": now.isoformat(),
    }
    if e and e.get("gambar"):
        embed["image"] = {"url": e["gambar"]}
    if HALAMAN_URL:
        embed["url"] = HALAMAN_URL
        embed["description"] += f"\n\n🔴 [Lihat countdown live (beranimasi)]({HALAMAN_URL})"
    return {"embeds": [embed], "allowed_mentions": {"parse": []}}


def baca_webhook():
    url = os.environ.get("DISCORD_WEBHOOK_COUNTDOWN", "").strip()
    if not url:
        try:
            url = open(WEBHOOK_FILE, encoding="utf-8").read().strip()
        except FileNotFoundError:
            url = ""
    if not url.startswith(("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/")):
        raise SystemExit("Webhook countdown belum ada / tidak valid. Isi secret DISCORD_WEBHOOK_COUNTDOWN "
                         "(GitHub) atau jalankan pasang_countdown.py (laptop).")
    return url


def muat_state():
    try:
        data = json.load(open(STATE_FILE, encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def simpan_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)


def _tunggu_429(e):
    try:
        return float(json.loads(e.read().decode()).get("retry_after", 2)) + 0.5
    except Exception:
        return 2.5


def kirim(webhook, payload):
    """Kirim pesan baru. Kembalikan id pesan, atau None kalau gagal."""
    kirim_payload = dict(payload, username=USERNAME)
    for _ in range(3):
        try:
            r = http_json(webhook + "?wait=true", kirim_payload)
            return str(r["id"]) if isinstance(r, dict) and r.get("id") else None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(_tunggu_429(e))
                continue
            print(f"  gagal kirim (HTTP {e.code})")
            return None
        except Exception as e:
            print(f"  gagal kirim: {e}")
            return None
    return None


def edit(webhook, mid, payload):
    """Edit pesan lama. Kembalikan 'ok', 'hilang' (pesan sudah dihapus), atau 'gagal'."""
    for _ in range(3):
        try:
            http_json(f"{webhook}/messages/{mid}", payload, method="PATCH")
            return "ok"
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(_tunggu_429(e))
                continue
            if e.code == 404:
                return "hilang"
            print(f"  gagal edit (HTTP {e.code})")
            return "gagal"
        except Exception as e:
            print(f"  gagal edit: {e}")
            return "gagal"
    return "gagal"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lihat", action="store_true", help="tampilkan isi embed tanpa mengirim")
    ap.add_argument("--sekarang", help="simulasi waktu, contoh 2026-12-20T12:00 (UTC)")
    args = ap.parse_args()

    if args.sekarang:
        now = datetime.fromisoformat(args.sekarang)
        now = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
    else:
        now = datetime.now(timezone.utc)

    payload = buat_payload(muat_event(), now)
    if args.lihat:
        print(json.dumps(payload["embeds"][0], ensure_ascii=False, indent=2))
        return

    webhook = baca_webhook()
    mid = muat_state().get("mid")
    if mid:
        hasil = edit(webhook, mid, payload)
        if hasil == "ok":
            print("Pesan countdown diperbarui.")
            return
        if hasil == "gagal":
            raise SystemExit(1)
        print("Pesan lama sudah dihapus, kirim yang baru.")

    mid = kirim(webhook, payload)
    if not mid:
        raise SystemExit(1)
    simpan_state({"mid": mid})
    print("Pesan countdown dikirim (id tersimpan di countdown_state.json).")


if __name__ == "__main__":
    main()
