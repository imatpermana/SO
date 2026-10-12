#!/usr/bin/env python3
"""uji_otomatis.py : menjalankan skenario uji TK-1A dan mencetak tabel hasil.

Jalankan dari folder yang sama dengan server.py:
  python3 uji_otomatis.py
Skrip menyalakan server sendiri di port 9100 dan membuat log di folder sementara,
jadi tidak mengganggu server yang sedang berjalan di port 9000.
"""
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time

from uji_beban import jalankan_beban

PORT = 9100
JUMLAH_KIRIM = [0]  # penghitung seluruh permintaan yang dikirim
FOLDER = os.path.dirname(os.path.abspath(__file__))


def tanya(perintah_list):
    """Satu koneksi, beberapa perintah. Mengembalikan daftar balasan."""
    hasil = []
    JUMLAH_KIRIM[0] += len(perintah_list)
    with socket.create_connection(("127.0.0.1", PORT), timeout=5) as s:
        buf = b""
        for p in perintah_list:
            s.sendall((p + "\n").encode())
            while b"\n" not in buf:
                buf += s.recv(1024)
            baris, buf = buf.split(b"\n", 1)
            hasil.append(baris.decode().strip())
    return hasil


def tunggu_server():
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", PORT), timeout=0.2).close()
            return True
        except OSError:
            time.sleep(0.1)
    return False


def main():
    kerja = tempfile.mkdtemp(prefix="tk1_")
    proc = subprocess.Popen(
        [sys.executable, os.path.join(FOLDER, "server.py"), "--port", str(PORT)],
        cwd=kerja, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if not tunggu_server():
        print("Server tidak bisa dijalankan")
        proc.kill()
        sys.exit(1)

    tabel = []  # (skenario, diharapkan, aktual, lulus)
    def uji(nama, diharapkan, aktual, lulus):
        tabel.append((nama, diharapkan, aktual, lulus))

    r = tanya(["CEK SO-A"])
    uji("CEK kelas yang ada", "200 OK SO-A Senin 08.00-09.40 Lab2", r[0], r[0] == "200 OK SO-A Senin 08.00-09.40 Lab2")
    r = tanya(["cek so-a"])
    uji("Perintah huruf kecil", "200 OK SO-A ...", r[0], r[0].startswith("200 OK SO-A"))
    r = tanya(["CEK XX-9"])
    uji("CEK kelas yang tidak ada", "404 KELAS XX-9 TIDAK DITEMUKAN", r[0], r[0] == "404 KELAS XX-9 TIDAK DITEMUKAN")
    r = tanya(["HARI Senin"])
    uji("HARI dengan 2 kelas", "200 OK AI-A,SO-A", r[0], r[0] == "200 OK AI-A,SO-A")
    r = tanya(["HARI Minggu"])
    uji("HARI tanpa kelas", "404 ...", r[0], r[0].startswith("404"))
    r = tanya(["HAPUS SO-A"])
    uji("Perintah tidak dikenal", "400 PERINTAH TIDAK DIKENAL", r[0], r[0] == "400 PERINTAH TIDAK DIKENAL")
    r = tanya([""])
    uji("Perintah kosong", "400 PERINTAH KOSONG", r[0], r[0] == "400 PERINTAH KOSONG")
    r = tanya(["CEK SO-A", "HARI Kamis", "KELUAR"])
    uji("3 perintah dalam satu koneksi", "200, 200, 200", ", ".join(x[:3] for x in r), [x[:3] for x in r] == ["200", "200", "200"])

    b = jalankan_beban("127.0.0.1", PORT, 50, 10)
    JUMLAH_KIRIM[0] += 500
    uji("50 klien paralel x 10 permintaan", "500 balasan 200, 0 galat",
        "%d balasan 200, %d galat (%.0f req/s)" % (b["berhasil_200"], b["galat_koneksi"], b["rps"]),
        b["berhasil_200"] == 500 and b["galat_koneksi"] == 0)

    proc.send_signal(signal.SIGTERM)
    try:
        keluaran, _ = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        keluaran = ""
    uji("Server berhenti rapi lewat SIGTERM", "kode keluar 0", "kode keluar %s" % proc.returncode, proc.returncode == 0)

    dikirim = JUMLAH_KIRIM[0]
    with open(os.path.join(kerja, "access.log"), encoding="utf-8") as f:
        baris = f.read().splitlines()
    uji("Semua permintaan tercatat lewat pipe", "%d baris log" % dikirim, "%d baris log" % len(baris), len(baris) == dikirim)
    utuh = all(len(x.split("|")) == 5 for x in baris)
    uji("Setiap baris log utuh (5 kolom)", "semua baris utuh", "semua utuh" if utuh else "ada baris rusak", utuh)
    uji("Pemroses log menerima EOF dan selesai", "pesan EOF muncul", "ada" if "EOF pada pipe" in keluaran else "tidak ada", "EOF pada pipe" in keluaran)

    print("\n%-3s %-40s %-36s %-40s %s" % ("No", "Skenario uji", "Hasil diharapkan", "Hasil aktual", "Status"))
    print("-" * 130)
    for i, (n, d, a, ok) in enumerate(tabel, 1):
        print("%-3d %-40s %-36s %-40s %s" % (i, n[:40], d[:36], a[:40], "Lulus" if ok else "GAGAL"))
    lulus = sum(1 for t in tabel if t[3])
    print("-" * 130)
    print("Ringkasan: %d lulus, %d gagal, dari %d skenario. Log sementara: %s" % (lulus, len(tabel) - lulus, len(tabel), kerja))
    sys.exit(0 if lulus == len(tabel) else 1)


if __name__ == "__main__":
    main()
