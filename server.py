#!/usr/bin/env python3
"""server.py : layanan cek jadwal kuliah (TK-1A, Sistem Operasi).

Dua jalur IPC yang dipakai:
  1. Socket TCP antara klien dan server (message passing lewat jaringan).
  2. Pipe anonim antara server (induk) dan pemroses log (anak), satu arah.

Jalankan:
  python3 server.py              # mendengar di 127.0.0.1:9000
  python3 server.py --port 9100
Hentikan dengan Ctrl+C atau kill -TERM <pid server>.
"""
import argparse
import os
import signal
import socket
import threading
import time

BERKAS_LOG = "access.log"
BERKAS_RINGKASAN = "ringkasan_log.txt"

# Data jadwal fiktif untuk keperluan tugas
JADWAL = {
    "SO-A": ("Senin", "08.00-09.40", "Lab2"),
    "ASD-A": ("Selasa", "10.00-11.40", "R3.1"),
    "JARKOM-B": ("Rabu", "13.00-14.40", "R2.4"),
    "BASDAT-A": ("Kamis", "08.00-09.40", "Lab1"),
    "PBO-C": ("Jumat", "09.00-10.40", "R3.2"),
    "AI-A": ("Senin", "13.00-14.40", "R3.3"),
}


# ---------------------------------------------------------------- pemroses log
def pemroses_log(fd_baca):
    """Proses anak. Membaca baris log dari pipe, menyimpannya ke berkas,
    lalu membuat ringkasan setelah pipe ditutup (EOF)."""
    per_status = {}
    per_perintah = {}
    total = 0
    sisa = b""
    with open(BERKAS_LOG, "a", buffering=1, encoding="utf-8") as berkas:
        while True:
            data = os.read(fd_baca, 4096)
            if not data:  # EOF: semua ujung tulis sudah ditutup
                break
            sisa += data
            *baris, sisa = sisa.split(b"\n")
            for b in baris:
                teks = b.decode("utf-8", "replace")
                berkas.write(teks + "\n")
                kolom = teks.split("|")
                if len(kolom) == 5:
                    per_status[kolom[3]] = per_status.get(kolom[3], 0) + 1
                    kata = kolom[2].split()
                    kunci = kata[0].upper() if kata else "(kosong)"
                    per_perintah[kunci] = per_perintah.get(kunci, 0) + 1
                total += 1
    os.close(fd_baca)
    with open(BERKAS_RINGKASAN, "w", encoding="utf-8") as r:
        r.write("Total baris log : %d\n" % total)
        for k in sorted(per_status):
            r.write("Status %s      : %d\n" % (k, per_status[k]))
        for k in sorted(per_perintah):
            r.write("Perintah %-6s : %d\n" % (k, per_perintah[k]))
    print("[pemroses_log pid=%d] EOF pada pipe, %d baris ditulis ke %s"
          % (os.getpid(), total, BERKAS_LOG), flush=True)


# --------------------------------------------------------------------- server
def catat(fd_tulis, alamat, perintah, status, ms):
    """Kirim satu baris log ke pemroses log lewat pipe.
    Satu os.write dengan panjang kurang dari PIPE_BUF (4096 byte) bersifat
    atomik, jadi baris dari banyak thread tidak saling bercampur."""
    waktu = time.strftime("%Y-%m-%dT%H:%M:%S")
    aman = perintah.replace("|", "/")[:100]
    baris = "%s|%s:%d|%s|%s|%.2f\n" % (waktu, alamat[0], alamat[1], aman, status, ms)
    os.write(fd_tulis, baris.encode("utf-8"))


def proses(perintah):
    """Mengembalikan (kode status, balasan)."""
    bagian = perintah.split()
    if not bagian:
        return "400", "400 PERINTAH KOSONG"
    cmd = bagian[0].upper()
    if cmd == "CEK" and len(bagian) == 2:
        kode = bagian[1].upper()
        data = JADWAL.get(kode)
        if data is None:
            return "404", "404 KELAS %s TIDAK DITEMUKAN" % kode
        return "200", "200 OK %s %s %s %s" % ((kode,) + data)
    if cmd == "HARI" and len(bagian) == 2:
        hasil = [k for k, v in JADWAL.items() if v[0].lower() == bagian[1].lower()]
        if not hasil:
            return "404", "404 TIDAK ADA KELAS PADA HARI %s" % bagian[1]
        return "200", "200 OK " + ",".join(sorted(hasil))
    if cmd == "KELUAR":
        return "200", "200 SAMPAI JUMPA"
    return "400", "400 PERINTAH TIDAK DIKENAL"


def layani(conn, alamat, fd_tulis):
    """Satu thread per koneksi klien. Protokol berbasis baris."""
    with conn:
        buf = b""
        while True:
            try:
                data = conn.recv(1024)
            except OSError:
                return
            if not data:  # klien menutup koneksi
                return
            buf += data
            while b"\n" in buf:
                baris, buf = buf.split(b"\n", 1)
                perintah = baris.decode("utf-8", "replace").strip()
                mulai = time.perf_counter()
                status, balasan = proses(perintah)
                try:
                    conn.sendall((balasan + "\n").encode("utf-8"))
                except OSError:
                    return
                catat(fd_tulis, alamat, perintah, status,
                      (time.perf_counter() - mulai) * 1000)
                if perintah.upper() == "KELUAR":
                    return


def main():
    ap = argparse.ArgumentParser(description="Server jadwal kuliah (socket dan pipe)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9000)
    arg = ap.parse_args()

    # 1. Buat pipe lalu fork SEBELUM thread dibuat.
    fd_baca, fd_tulis = os.pipe()
    pid_log = os.fork()
    if pid_log == 0:
        os.close(fd_tulis)  # anak hanya membaca. Jika ujung tulis tidak ditutup, EOF tidak pernah datang
        signal.signal(signal.SIGINT, signal.SIG_IGN)  # anak menunggu EOF, tidak ikut mati saat Ctrl+C
        pemroses_log(fd_baca)
        os._exit(0)
    os.close(fd_baca)  # induk hanya menulis

    # 2. Socket TCP untuk klien
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((arg.host, arg.port))
    srv.listen(64)
    srv.settimeout(0.5)

    berhenti = threading.Event()
    signal.signal(signal.SIGINT, lambda s, f: berhenti.set())
    signal.signal(signal.SIGTERM, lambda s, f: berhenti.set())
    print("[server pid=%d] mendengar di %s:%d, pemroses log pid=%d"
          % (os.getpid(), arg.host, arg.port, pid_log), flush=True)

    threads = []
    while not berhenti.is_set():
        try:
            conn, alamat = srv.accept()
        except socket.timeout:
            continue
        t = threading.Thread(target=layani, args=(conn, alamat, fd_tulis), daemon=True)
        t.start()
        threads.append(t)
        threads = [x for x in threads if x.is_alive()]

    # 3. Penutupan rapi: tunggu thread, tutup ujung tulis, tunggu pemroses log
    srv.close()
    for t in threads:
        t.join(timeout=2)
    os.close(fd_tulis)  # pemroses log kini menerima EOF
    os.waitpid(pid_log, 0)
    print("[server pid=%d] berhenti" % os.getpid(), flush=True)


if __name__ == "__main__":
    main()
