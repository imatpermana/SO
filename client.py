#!/usr/bin/env python3
"""client.py : klien layanan cek jadwal kuliah (TK-1A).

Contoh:
  python3 client.py CEK SO-A
  python3 client.py HARI Senin
  python3 client.py            # mode interaktif, ketik KELUAR untuk selesai
"""
import argparse
import socket


def baca_balasan(sock):
    """Membaca sampai satu baris lengkap (berakhir newline)."""
    buf = b""
    while b"\n" not in buf:
        data = sock.recv(1024)
        if not data:
            break
        buf += data
    return buf.decode("utf-8", "replace").strip()


def kirim(sock, perintah):
    sock.sendall((perintah + "\n").encode("utf-8"))
    return baca_balasan(sock)


def main():
    ap = argparse.ArgumentParser(description="Klien jadwal kuliah")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("perintah", nargs="*", help="contoh: CEK SO-A")
    arg = ap.parse_args()

    with socket.create_connection((arg.host, arg.port), timeout=5) as s:
        if arg.perintah:
            print(kirim(s, " ".join(arg.perintah)))
            return
        print("Terhubung ke %s:%d. Contoh: CEK SO-A, HARI Senin, KELUAR" % (arg.host, arg.port))
        while True:
            try:
                p = input("> ").strip()
            except EOFError:
                break
            print(kirim(s, p))
            if p.upper() == "KELUAR":
                break


if __name__ == "__main__":
    main()
