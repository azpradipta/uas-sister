# Skrip Demo Lengkap UAS

File ini dibuat supaya demo bisa diikuti dari awal sampai akhir. Formatnya:

- "Bacakan" = narasi yang kamu ucapkan di video.
- "Lakukan" = aksi yang kamu lakukan di terminal/browser.
- "Copas" = command PowerShell yang bisa langsung dicopy.
- "Tunjukkan" = bagian output yang perlu disorot.

Durasi target: 25 sampai 35 menit.

## Persiapan Sebelum Record

Pastikan:

- Docker Desktop sudah running.
- Terminal memakai PowerShell.
- Kamu berada di folder project.
- Port `8080` tidak dipakai aplikasi lain.
- Browser boleh dibuka ke `http://localhost:8080/docs` jika ingin menunjukkan Swagger UI.

Copas untuk masuk folder project:

```powershell
Set-Location 'D:\Kuliah\Semester 6\Sistem Paralel dan Terdistribusi\uas-sister'
```

Opsional untuk rehearsal bersih. Jangan pakai kalau masih ingin menyimpan data demo sebelumnya:

```powershell
docker compose down -v
```

Install dependency test lokal jika belum pernah:

```powershell
python -m pip install -r requirements-dev.txt
```

## 0:00 - 1:30 Pembukaan

Bacakan:

> Halo, saya [nama], pada video ini saya mendemokan proyek UAS Sistem Terdistribusi dengan tema Pub-Sub Log Aggregator Terdistribusi. Sistem ini dibuat dengan Python, FastAPI, Redis Streams, PostgreSQL, dan Docker Compose. Fokus utama implementasi ini adalah idempotent consumer, deduplication persisten, transaksi database, dan kontrol konkurensi agar event yang sama tidak diproses dua kali walaupun dikirim berulang atau diproses oleh beberapa worker paralel.

> Demo ini akan menunjukkan arsitektur multi-service, cara menjalankan Docker Compose, publish event normal dan duplikat, statistik, audit log, uji concurrency melalui publisher, persistence setelah container recreate, serta test suite.

## 1:30 - 4:00 Jelaskan Struktur Project

Lakukan:

Tampilkan daftar file utama.

Copas:

```powershell
Get-ChildItem
```

Bacakan:

> Struktur project terdiri dari folder `aggregator`, `publisher`, `tests`, `docker-compose.yml`, `README.md`, `report.md`, dan file panduan demo. Folder `aggregator` berisi API FastAPI, consumer worker, koneksi Redis Streams, dan storage transaction logic. Folder `publisher` berisi simulator event yang dapat mengirim event batch dengan duplicate rate tertentu. Folder `tests` berisi 20 test untuk validasi schema, deduplication, persistence, concurrency, stats, dan API.

Tampilkan file penting:

```powershell
Get-ChildItem .\aggregator\app
Get-ChildItem .\publisher
Get-ChildItem .\tests
```

Bacakan:

> File paling penting untuk correctness adalah `database.py`, karena di sana ada transaksi dan unique constraint. `consumer.py` berisi worker paralel yang membaca Redis Streams. `queue.py` berisi operasi Redis Streams, sedangkan `main.py` berisi endpoint API.

## 4:00 - 7:00 Jelaskan Arsitektur Docker Compose

Lakukan:

Tampilkan isi Compose.

Copas:

```powershell
Get-Content .\docker-compose.yml
```

Bacakan:

> Compose menjalankan empat service. Pertama, `aggregator`, yaitu service FastAPI yang expose port `8080` ke host untuk demo lokal. Kedua, `publisher`, yaitu service simulator untuk mengirim event dalam jumlah besar. Ketiga, `broker`, yaitu Redis Streams sebagai message broker internal. Keempat, `storage`, yaitu PostgreSQL 16 sebagai database persisten.

> Redis dan PostgreSQL tidak membuka port ke host, sehingga aksesnya hanya melalui jaringan Compose. Aggregator terhubung ke network `backend` untuk berkomunikasi dengan Redis dan PostgreSQL, serta network `edge` agar API dapat diakses dari localhost saat demo.

> Data PostgreSQL disimpan di named volume `pg_data`. Ini penting untuk membuktikan bahwa deduplication tetap ada walaupun container aggregator dihapus atau dibuat ulang.

## 7:00 - 10:00 Build dan Jalankan Stack

Lakukan:

Build dan jalankan service utama.

Copas:

```powershell
docker compose up --build -d aggregator
```

Tunggu sampai selesai, lalu cek status:

```powershell
docker compose ps
```

Bacakan:

> Di sini terlihat tiga service utama sedang berjalan: aggregator, broker Redis, dan storage PostgreSQL. Aggregator memiliki port mapping `8080`, sedangkan Redis dan PostgreSQL hanya terlihat sebagai port internal container. Ini menunjukkan bahwa akses eksternal untuk demo hanya lewat API aggregator.

Tunjukkan readiness:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8080/readyz'
```

Bacakan:

> Endpoint `/readyz` memastikan aggregator bisa terhubung ke database dan Redis. Kalau statusnya `ready`, berarti service sudah siap menerima event.

Tampilkan stats awal:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8080/stats' | ConvertTo-Json -Depth 10
```

Bacakan:

> Endpoint `/stats` menampilkan jumlah processing attempt yang diterima worker, jumlah event unik yang berhasil diproses, jumlah duplicate yang dibuang, duplicate rate, daftar topic, dan uptime.

## 10:00 - 12:00 Buka Browser untuk Swagger UI

Lakukan:

Buka Swagger UI FastAPI di browser.

Copas:

```powershell
Start-Process 'http://localhost:8080/docs'
```

Bacakan:

> Saya buka Swagger UI dari FastAPI di browser. Ini menunjukkan bahwa aggregator benar-benar berjalan sebagai web API di `localhost:8080`. Di sini terlihat endpoint utama: `POST /publish`, `GET /events`, `GET /stats`, `GET /audit`, `/healthz`, dan `/readyz`.

Tunjukkan di browser:

- `POST /publish`
- `GET /events`
- `GET /stats`
- `GET /audit`
- `GET /readyz`

Lakukan:

Buka endpoint stats langsung di browser.

Copas:

```powershell
Start-Process 'http://localhost:8080/stats'
```

Bacakan:

> Endpoint ini juga bisa dibuka langsung dari browser karena output-nya JSON. Namun untuk demo berikutnya saya tetap memakai PowerShell agar command dan hasilnya lebih mudah direkam dan direproduksi.

Setelah itu kembali ke VS Code atau PowerShell.

## 12:00 - 15:00 Publish Event Manual

Lakukan:

Kirim satu event manual.

Copas:

```powershell
$event1 = @{
  topic = 'auth.login'
  event_id = 'manual-demo-1'
  timestamp = '2026-01-01T00:00:00Z'
  source = 'manual-demo'
  payload = @{
    level = 'INFO'
    message = 'login pertama'
  }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri 'http://localhost:8080/publish' -Method Post -ContentType 'application/json' -Body $event1
```

Bacakan:

> Request ini mengirim satu event dengan topic `auth.login` dan event id `manual-demo-1`. Endpoint `/publish` hanya menerima dan memasukkan event ke Redis Streams. Pemrosesan dedup dilakukan secara asynchronous oleh worker.

Tunggu sebentar:

```powershell
Start-Sleep -Seconds 2
```

Cek event:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8080/events?topic=auth.login&limit=5' | ConvertTo-Json -Depth 10
```

Bacakan:

> Event sudah muncul di `/events`, artinya worker berhasil membaca queue dan menyimpan event unik ke PostgreSQL.

Cek stats:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8080/stats' | ConvertTo-Json -Depth 10
```

Bacakan:

> Setelah satu event unik, `received` naik, `unique_processed` naik, dan `duplicate_dropped` masih nol atau belum bertambah.

## 15:00 - 18:00 Bukti Idempotency dan Deduplication

Lakukan:

Kirim event dengan topic dan event_id yang sama.

Copas:

```powershell
$duplicate1 = @{
  topic = 'auth.login'
  event_id = 'manual-demo-1'
  timestamp = '2026-01-01T00:00:00Z'
  source = 'manual-demo'
  payload = @{
    level = 'WARN'
    message = 'ini duplikat dan harus di-drop'
  }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri 'http://localhost:8080/publish' -Method Post -ContentType 'application/json' -Body $duplicate1
```

Tunggu:

```powershell
Start-Sleep -Seconds 2
```

Cek stats:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8080/stats' | ConvertTo-Json -Depth 10
```

Bacakan:

> Sekarang `received` naik karena worker memang menerima processing attempt baru. Tetapi `unique_processed` tidak naik untuk event yang sama. Yang naik adalah `duplicate_dropped`. Ini membuktikan idempotent consumer: event boleh dikirim ulang, tetapi efek pemrosesan unik hanya terjadi satu kali.

Cek audit:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8080/audit?limit=5' | ConvertTo-Json -Depth 10
```

Bacakan:

> Audit log menunjukkan dua status: event pertama `processed`, dan event kedua `duplicate`. Detail duplicate menjelaskan bahwa event diabaikan oleh unique constraint.

Tampilkan event unik lagi:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8080/events?topic=auth.login&limit=10' | ConvertTo-Json -Depth 10
```

Bacakan:

> Walaupun event dengan id yang sama dikirim dua kali, daftar `/events` tetap hanya menyimpan satu event unik untuk topic dan event id tersebut.

Opsional, buka hasil event di browser:

```powershell
Start-Process 'http://localhost:8080/events?topic=auth.login&limit=10'
```

Bacakan:

> Di browser juga terlihat bahwa endpoint `/events` hanya mengembalikan event unik yang sudah diproses.

## 18:00 - 22:00 Jelaskan Transaksi dan Kontrol Konkurensi dari Kode

Lakukan:

Tampilkan bagian unique constraint.

Copas:

```powershell
Select-String -Path .\aggregator\app\database.py -Pattern 'UniqueConstraint|uq_processed_topic_event_id' -Context 3,3
```

Bacakan:

> Deduplication utama dilakukan oleh unique constraint `(topic, event_id)`. Artinya database tidak mengizinkan dua record dengan topic dan event id yang sama. Ini lebih aman daripada hanya mengecek duplikat di memori aplikasi, karena memori akan hilang saat container restart.

Tampilkan bagian transaksi process_event:

```powershell
Select-String -Path .\aggregator\app\database.py -Pattern 'async def process_event|on_conflict_do_nothing|unique_processed|duplicate_dropped' -Context 3,5
```

Bacakan:

> Pada fungsi `process_event`, worker membuka transaksi database. Di dalam transaksi ini, counter `received` dinaikkan, lalu sistem mencoba insert event ke tabel `processed_events`. Insert memakai `ON CONFLICT DO NOTHING`, sehingga kalau event sudah ada, database tidak membuat baris baru. Setelah itu sistem menaikkan counter `unique_processed` atau `duplicate_dropped`, lalu menulis audit log.

> Isolation level PostgreSQL yang dipakai adalah `READ COMMITTED`. Untuk kasus ini, correctness tidak hanya bergantung pada isolation level, tetapi pada unique constraint dan atomic upsert. Jadi ketika dua worker memproses event yang sama secara paralel, database menjadi arbiter: hanya satu insert yang berhasil.

Tampilkan worker ack:

```powershell
Select-String -Path .\aggregator\app\consumer.py -Pattern 'claim_stale|process_event|ack' -Context 2,4
```

Bacakan:

> Worker membaca pesan dari Redis Streams. Pesan baru di-ack setelah `process_event` selesai. Jika worker crash sebelum ack, pesan masih bisa diklaim ulang oleh worker lain. Karena consumer idempotent, pemrosesan ulang tidak menyebabkan side effect ganda.

## 22:00 - 26:00 Load Test dengan Publisher Compose

Lakukan:

Jalankan publisher. Untuk video, boleh mulai dengan 3000 agar cepat. Untuk memenuhi requirement performa, jalankan juga 20.000 dan catat hasilnya di laporan.

Versi cepat untuk demo:

```powershell
docker compose --profile load run --rm `
  -e TOTAL_EVENTS=3000 `
  -e DUPLICATE_RATE=0.30 `
  -e BATCH_SIZE=500 `
  -e CONCURRENCY=4 `
  -e SOURCE=video-load `
  -e SEED=video-load `
  publisher
```

Versi requirement 20.000 event:

```powershell
docker compose --profile load run --rm `
  -e TOTAL_EVENTS=20000 `
  -e DUPLICATE_RATE=0.30 `
  -e BATCH_SIZE=500 `
  -e CONCURRENCY=4 `
  -e SOURCE=video-load-20k `
  -e SEED=video-load-20k `
  publisher
```

Bacakan:

> Publisher ini mengirim event dalam batch. Duplicate rate diset 0,30, artinya sekitar 30 persen event adalah duplikat. Untuk 20.000 event, ekspektasinya sekitar 14.000 event unik dan 6.000 event duplikat. Publisher juga menampilkan throughput dalam events per second.

Tunggu worker mengejar queue:

```powershell
for ($i = 1; $i -le 10; $i++) {
  Invoke-RestMethod -Uri 'http://localhost:8080/stats' | ConvertTo-Json -Depth 10
  Start-Sleep -Seconds 5
}
```

Bacakan:

> Karena sistem asynchronous, stats tidak harus langsung selesai pada detik yang sama dengan publisher. Worker akan terus membaca queue sampai semua event diproses. Kebenaran utama dilihat dari `unique_processed`, `duplicate_dropped`, dan isi `/events`.

Tampilkan log aggregator:

```powershell
docker compose logs aggregator --tail=50
```

Bacakan:

> Log menunjukkan event yang diproses dan duplicate yang di-drop. Ini bagian observability dari sistem.

## 26:00 - 30:00 Persistence Setelah Container Recreate

Bacakan:

> Sekarang saya membuktikan bahwa dedup store persisten. Saya akan mengirim event deterministic dengan `SEED`, lalu recreate container aggregator. Setelah itu saya kirim event yang sama lagi. Jika storage persisten bekerja, run kedua tidak akan menambah unique event untuk set yang sama.

Lakukan:

Run deterministic pertama:

```powershell
docker compose --profile load run --rm `
  -e TOTAL_EVENTS=1000 `
  -e DUPLICATE_RATE=0.30 `
  -e BATCH_SIZE=250 `
  -e CONCURRENCY=4 `
  -e SOURCE=demo-persistence `
  -e SEED=uas-persistence `
  publisher
```

Tunggu dan cek stats:

```powershell
Start-Sleep -Seconds 5
Invoke-RestMethod -Uri 'http://localhost:8080/stats' | ConvertTo-Json -Depth 10
```

Recreate aggregator:

```powershell
docker compose up -d --force-recreate aggregator
```

Cek ready:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8080/readyz'
```

Run deterministic kedua dengan source dan seed yang sama:

```powershell
docker compose --profile load run --rm `
  -e TOTAL_EVENTS=1000 `
  -e DUPLICATE_RATE=0.30 `
  -e BATCH_SIZE=250 `
  -e CONCURRENCY=4 `
  -e SOURCE=demo-persistence `
  -e SEED=uas-persistence `
  publisher
```

Tunggu dan cek stats:

```powershell
Start-Sleep -Seconds 5
Invoke-RestMethod -Uri 'http://localhost:8080/stats' | ConvertTo-Json -Depth 10
```

Bacakan:

> Run kedua memakai source dan seed yang sama, sehingga event id yang dihasilkan sama dengan run pertama. Setelah aggregator dibuat ulang, dedup tetap bekerja karena data unik disimpan di PostgreSQL volume `pg_data`, bukan di memori container aggregator. Pada run kedua, yang bertambah terutama `duplicate_dropped`, sedangkan unique untuk set event yang sama tidak diproses ulang.

## 30:00 - 33:00 Test Suite

Lakukan:

Jalankan test.

Copas:

```powershell
python -m pytest -q
```

Bacakan:

> Test suite berisi 20 test. Cakupannya meliputi validasi schema event, single dan batch publish, dedup event duplikat, event id sama pada topic berbeda, persistence dedup state setelah storage dibuka ulang, concurrency 50 proses untuk event yang sama, stress kecil 300 event, dan konsistensi endpoint stats.

Tunjukkan:

```text
20 passed
```

## 33:00 - 36:00 Hubungan ke Teori Bab 1-13

Bacakan:

> Dari Bab 1 dan 2, sistem ini menunjukkan karakteristik sistem terdistribusi dan arsitektur microservices. Komponen publisher, aggregator, broker, dan storage berjalan terpisah dan berkomunikasi melalui jaringan Compose.

> Dari Bab 3 dan 4, komunikasi dilakukan melalui HTTP dan Redis Streams. Penamaan event menggunakan `topic` dan `event_id`, sehingga deduplication memiliki identity yang jelas.

> Dari Bab 5, ordering tidak menggunakan total ordering global karena mahal dan tidak diperlukan untuk log aggregator. Sistem memakai timestamp dari producer dan logical sequence dari database.

> Dari Bab 6, sistem menghadapi failure mode seperti duplicate event, retry, worker crash, dan container recreate. Mitigasinya adalah Redis Streams, ack setelah transaksi, XAUTOCLAIM, dan dedup store persisten.

> Dari Bab 7, sistem bersifat eventually consistent karena publish dan consume asynchronous. Setelah event diterima, worker memprosesnya sampai state database konvergen ke kumpulan event unik.

> Penekanan utama ada pada Bab 8 dan 9: transaksi dan kontrol konkurensi. Sistem memakai transaksi database, isolation level READ COMMITTED, unique constraint, dan idempotent write pattern dengan `ON CONFLICT DO NOTHING`. Ini mencegah lost update dan race condition saat beberapa worker memproses event yang sama.

> Dari Bab 10 sampai 13, sistem menunjukkan storage persisten, isolasi jaringan Compose, endpoint web, healthcheck, readiness, observability melalui stats, audit, dan logs.

## 36:00 - 37:00 Penutup

Bacakan:

> Kesimpulannya, sistem ini menerima kenyataan bahwa distributed messaging sering bersifat at-least-once. Daripada memaksa exactly-once delivery yang sulit, sistem membuat consumer idempotent. Dengan key `(topic, event_id)`, unique constraint, transaksi database, dan dedup store persisten, event yang sama boleh datang berkali-kali tetapi efek pemrosesan unik hanya terjadi sekali.

> Demo ini sudah menunjukkan API publish, event unik, duplicate dropped, stats, audit log, worker paralel, Docker Compose, persistence setelah recreate, dan test suite.

## Checklist Setelah Record

Isi bagian ini di `report.md`:

- Nama.
- NIM.
- Link GitHub.
- Link YouTube.
- Metrik hasil 20.000 event:
  - total event yang dikirim publisher.
  - expected unique.
  - expected duplicate.
  - throughput dari output publisher.
  - stats akhir dari `/stats`.

Command untuk mematikan container tanpa hapus data:

```powershell
docker compose down
```

Command untuk menghapus semua data demo:

```powershell
docker compose down -v
```

## Troubleshooting Cepat

Kalau port 8080 sudah dipakai:

```powershell
docker compose down
```

Lalu cek aplikasi lain yang memakai port 8080, atau ubah port di `docker-compose.yml` dari `"8080:8080"` menjadi `"8081:8080"`.

Kalau `/readyz` belum ready:

```powershell
docker compose ps
docker compose logs aggregator --tail=80
docker compose logs storage --tail=80
docker compose logs broker --tail=80
```

Kalau publisher selesai tetapi stats belum lengkap:

```powershell
for ($i = 1; $i -le 12; $i++) {
  Invoke-RestMethod -Uri 'http://localhost:8080/stats' | ConvertTo-Json -Depth 10
  Start-Sleep -Seconds 5
}
```

Kalau ingin mulai ulang demo dari nol:

```powershell
docker compose down -v
docker compose up --build -d aggregator
```

Kalau pytest belum bisa jalan karena dependency belum ada:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```
