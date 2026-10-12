#!/usr/bin/env python3
"""uji_beban.py : mengirim banyak permintaan paralel ke server (TK-1A).

Contoh:
  python3 uji_beban.py -c 50 -n 20          # 50 klien x 20 permintaan
  python3 uji_beban.py --port 9100 -c 10 -n 5
"""
import argparse
import socket
import threading
import time

KELAS = ["SO-A", "ASD-A", "JARKOM-B", "BASDAT-A", "PBO-C", "AI-A"]


def satu_klien(host, port, n, hasil, idx):
    """Satu koneksi, n permintaan berurutan. Menyimpan latensi dan jumlah status 200."""
    lat = []
    ok = 0
    try:
        with socket.create_connection((host, port), timeout=10) as s:
            buf = b""
            for i in range(n):
                perintah = "CEK %s\n" % KELAS[(idx + i) % len(KELAS)]
                t0 = time.perf_counter()
                s.sendall(perintah.encode())
                while b"\n" not in buf:
                    data = s.recv(1024)
                    if not data:
                        raise ConnectionError("koneksi ditutup server")
                    buf += data
                baris, buf = buf.split(b"\n", 1)
                lat.append((time.perf_counter() - t0) * 1000)
                if baris.startswith(b"200"):
                    ok += 1
    except Exception as e:  # noqa: BLE001
        hasil[idx] = (lat, ok, str(e))
        return
    hasil[idx] = (lat, ok, None)


def jalankan_beban(host, port, klien, n):
    hasil = [None] * klien
    t0 = time.perf_counter()
    ths = [threading.Thread(target=satu_klien, args=(host, port, n, hasil, i)) for i in range(klien)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    durasi = time.perf_counter() - t0
    semua = [x for h in hasil if h for x in h[0]]
    ok = sum(h[1] for h in hasil if h)
    galat = [h[2] for h in hasil if h and h[2]]
    semua.sort()
    return {
        "klien": klien, "per_klien": n, "dikirim": klien * n,
        "berhasil_200": ok, "galat_koneksi": len(galat),
        "durasi_s": durasi, "rps": (len(semua) / durasi) if durasi else 0,
        "lat_rata_ms": (sum(semua) / len(semua)) if semua else 0,
        "lat_p95_ms": semua[int(0.95 * (len(semua) - 1))] if semua else 0,
        "lat_maks_ms": semua[-1] if semua else 0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("-c", "--klien", type=int, default=20)
    ap.add_argument("-n", "--per-klien", type=int, default=10)
    a = ap.parse_args()
    r = jalankan_beban(a.host, a.port, a.klien, a.per_klien)
    print("Klien paralel        : %d" % r["klien"])
    print("Permintaan per klien : %d" % r["per_klien"])
    print("Total dikirim        : %d" % r["dikirim"])
    print("Berhasil (status 200): %d" % r["berhasil_200"])
    print("Galat koneksi        : %d" % r["galat_koneksi"])
    print("Durasi total         : %.3f detik" % r["durasi_s"])
    print("Throughput           : %.0f permintaan/detik" % r["rps"])
    print("Latensi rata-rata    : %.2f ms" % r["lat_rata_ms"])
    print("Latensi p95          : %.2f ms" % r["lat_p95_ms"])
    print("Latensi maksimum     : %.2f ms" % r["lat_maks_ms"])


if __name__ == "__main__":
    main()
