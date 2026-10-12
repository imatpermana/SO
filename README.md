# TK-1A: Implementasi IPC pada Layanan Cek Jadwal Kuliah

Program klien-server untuk layanan cek jadwal kuliah (tema Server Layanan Akademik Kampus).
Mata kuliah Sistem Operasi, Kelas A.

## Mekanisme IPC

| Jalur | Mekanisme | Arah |
|---|---|---|
| Klien dan server | Socket TCP (message passing lewat jaringan) | dua arah |
| Server dan pemroses log | Pipe anonim (message passing lewat kernel) | satu arah, server ke pemroses log |

Server membuat pipe lalu `fork()` sebelum membuat thread. Proses anak menjadi pemroses log
yang membaca baris log dari pipe dan menyimpannya ke `access.log`. Server membuat satu thread
untuk tiap koneksi klien.

## Berkas

| Berkas | Fungsi |
|---|---|
| `server.py` | Server socket TCP, pembuat pipe, dan pemroses log |
| `client.py` | Klien baris perintah dan mode interaktif |
| `uji_beban.py` | Mengirim banyak permintaan paralel dan mengukur latensi |
| `uji_otomatis.py` | Menjalankan 13 skenario uji dan mencetak tabel hasil |

## Cara menjalankan

Kebutuhan: Python 3 (diuji pada Python 3.13, tidak memakai pustaka tambahan).

```
python3 server.py                 # terminal 1, mendengar di 127.0.0.1:9000
python3 client.py CEK SO-A        # terminal 2
python3 client.py HARI Senin
python3 client.py                 # mode interaktif, akhiri dengan KELUAR
python3 uji_beban.py -c 20 -n 50  # 20 klien x 50 permintaan
python3 uji_otomatis.py           # uji otomatis pada port 9100
```

Hentikan server dengan Ctrl+C atau `kill -TERM <pid server>`. Setelah server berhenti,
pemroses log menerima EOF lalu menulis `ringkasan_log.txt`.

## Protokol

Satu perintah per baris, diakhiri newline.

| Perintah | Balasan |
|---|---|
| `CEK <kode kelas>` | `200 OK <kode> <hari> <jam> <ruang>` atau `404 KELAS <kode> TIDAK DITEMUKAN` |
| `HARI <nama hari>` | `200 OK <daftar kelas>` atau `404 TIDAK ADA KELAS PADA HARI <hari>` |
| `KELUAR` | `200 SAMPAI JUMPA` lalu koneksi ditutup |
| lainnya | `400 PERINTAH TIDAK DIKENAL` atau `400 PERINTAH KOSONG` |

## Format log (`access.log`)

```
waktu|alamat klien:port|perintah|status|lama proses (ms)
```
