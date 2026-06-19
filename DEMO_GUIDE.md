# Panduan Video Demo 25 Menit

Isi link video di `report.md` dan README setelah upload ke YouTube unlisted/public.

## 0:00 - 3:00 Pembukaan dan Arsitektur

Jelaskan bahwa sistem ini adalah pub-sub log aggregator terdistribusi.

Narasi singkat:

- Publisher tidak menulis langsung ke database.
- Publisher mengirim event ke aggregator lewat `POST /publish`.
- Aggregator memasukkan event ke Redis Streams sebagai broker internal.
- Beberapa worker aggregator membaca stream secara paralel.
- Storage PostgreSQL menyimpan event unik dan audit secara persisten.
- Dedup terjadi di database dengan unique constraint `(topic, event_id)`.

Tampilkan:

```powershell
Get-ChildItem
Get-Content docker-compose.yml
```

## 3:00 - 6:00 Build dan Run Compose

Jalankan:

```powershell
docker compose up --build -d aggregator
docker compose ps
curl.exe http://localhost:8080/readyz
```

Tekankan bahwa Redis dan PostgreSQL tidak expose port host. Yang expose hanya aggregator di `8080`.

## 6:00 - 9:00 Endpoint Dasar

Tampilkan stats awal:

```powershell
curl.exe http://localhost:8080/stats
```

Kirim event manual:

```powershell
curl.exe -X POST http://localhost:8080/publish `
  -H "Content-Type: application/json" `
  -d "{\"topic\":\"auth.login\",\"event_id\":\"manual-demo-1\",\"timestamp\":\"2026-01-01T00:00:00Z\",\"source\":\"manual\",\"payload\":{\"message\":\"first\"}}"
```

Lihat hasil:

```powershell
curl.exe "http://localhost:8080/events?topic=auth.login&limit=5"
curl.exe http://localhost:8080/stats
```

## 9:00 - 13:00 Bukti Idempotency dan Dedup

Kirim event manual yang sama beberapa kali:

```powershell
curl.exe -X POST http://localhost:8080/publish `
  -H "Content-Type: application/json" `
  -d "{\"topic\":\"auth.login\",\"event_id\":\"manual-demo-1\",\"timestamp\":\"2026-01-01T00:00:00Z\",\"source\":\"manual\",\"payload\":{\"message\":\"duplicate\"}}"
```

Tampilkan:

```powershell
curl.exe http://localhost:8080/stats
curl.exe "http://localhost:8080/audit?limit=5"
```

Narasi:

- `received` naik karena pesan memang diterima/dikonsumsi.
- `unique_processed` tidak naik untuk event yang sama.
- `duplicate_dropped` naik.
- Di audit terlihat status `duplicate`.

## 13:00 - 17:00 Load 20.000 Event dan Konkurensi

Jalankan publisher:

```powershell
docker compose --profile load run --rm publisher
```

Tunggu beberapa detik, lalu:

```powershell
curl.exe http://localhost:8080/stats
docker compose logs aggregator --tail=50
```

Narasi:

- Publisher mengirim 20.000 event.
- Default duplicate rate 30 persen, jadi ekspektasi sekitar 14.000 unique dan 6.000 duplicate.
- Worker count default 6, sehingga beberapa worker memproses stream secara paralel.
- Race condition dicegah oleh transaksi database dan unique constraint.

Opsional K6:

```powershell
docker compose --profile k6 run --rm k6
```

Narasi:

- K6 disediakan sebagai HTTP load testing tambahan.
- K6 menembak `POST /publish` dari jaringan Compose.
- Publisher Python tetap dipakai sebagai simulator domain event, sedangkan K6 dipakai untuk menunjukkan rate, latency, dan error rate HTTP.

## 17:00 - 21:00 Crash/Recreate dan Persistence

Run deterministic pertama:

```powershell
docker compose --profile load run --rm `
  -e TOTAL_EVENTS=1000 `
  -e DUPLICATE_RATE=0.30 `
  -e SOURCE=demo-persistence `
  -e SEED=uas-demo `
  publisher
```

Recreate aggregator:

```powershell
docker compose up -d --force-recreate aggregator
curl.exe http://localhost:8080/readyz
```

Run deterministic kedua:

```powershell
docker compose --profile load run --rm `
  -e TOTAL_EVENTS=1000 `
  -e DUPLICATE_RATE=0.30 `
  -e SOURCE=demo-persistence `
  -e SEED=uas-demo `
  publisher
```

Tampilkan:

```powershell
curl.exe http://localhost:8080/stats
```

Narasi:

- Container aggregator boleh dibuat ulang.
- Data dedup tetap ada karena PostgreSQL memakai named volume `pg_data`.
- Run kedua memakai event_id yang sama karena `SEED` sama.
- Sistem tidak melakukan double-process.

## 21:00 - 23:00 Test Suite

Jalankan:

```powershell
python -m pytest -q
```

Jelaskan cakupan test:

- Validasi schema event.
- Dedup event duplikat.
- Persistence setelah storage dibuka ulang.
- Concurrency 50 proses untuk event yang sama.
- Stress kecil 300 event.
- API `/publish` dan `/stats`.

## 23:00 - 25:00 Hubungan Teori

Hubungkan ke bab:

- Bab 1-2: microservices dan publish-subscribe.
- Bab 3-4: komunikasi, topic, event_id.
- Bab 5: ordering memakai timestamp plus logical sequence.
- Bab 6: retry, Redis Streams, `XAUTOCLAIM`, crash recovery.
- Bab 7: eventual consistency karena publish dan consume asynchronous.
- Bab 8-9: transaksi, isolation, unique constraint, idempotent upsert.
- Bab 10-13: Compose network internal, volume, healthcheck, observability.

Kalimat penutup:

> Inti desain ini adalah menerima sifat at-least-once delivery di sistem terdistribusi, lalu membuat consumer idempotent dengan dedup store transaksional yang persisten.
