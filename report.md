# Laporan UAS Sistem Terdistribusi

Judul: Pub-Sub Log Aggregator Terdistribusi dengan Idempotent Consumer, Deduplication, dan Transaksi/Kontrol Konkurensi

Nama: [Isi nama]

NIM: [Isi NIM]

Repository GitHub: https://github.com/azpradipta/uas-sister

Video demo: https://youtu.be/BvaZYEFNVRY

Bahasa pemrograman: Python

Orkestrasi: Docker Compose

## Ringkasan Sistem

Sistem yang dibangun adalah pub-sub log aggregator multi-service. Publisher mengirim event JSON ke aggregator melalui endpoint `POST /publish`. Aggregator tidak langsung menyimpan event pada request thread, tetapi memasukkannya ke Redis Streams sebagai broker internal. Beberapa worker aggregator membaca stream secara paralel, lalu menyimpan event unik ke PostgreSQL. Deduplication dilakukan secara persisten menggunakan unique constraint `(topic, event_id)` pada tabel `processed_events`.

Desain ini menerima model at-least-once delivery. Artinya event boleh diterima lebih dari sekali karena retry, duplikasi publisher, pending message, atau crash sebelum ack. Konsistensi dijaga oleh idempotent consumer: event dengan `(topic, event_id)` yang sama hanya menghasilkan satu record unik. Semua update penting saat consumer memproses event berada dalam satu transaksi database: menaikkan counter `received`, mencoba insert event unik, menaikkan counter `unique_processed` atau `duplicate_dropped`, dan menulis audit log.

## Arsitektur Sistem

Komponen Docker Compose:

| Service | Peran |
|---|---|
| `aggregator` | FastAPI API, worker consumer internal, stats, audit log, health/readiness endpoint. |
| `publisher` | Generator event batch dengan duplikasi dan mode deterministic `SEED`. |
| `broker` | Redis Streams sebagai message broker internal. |
| `storage` | PostgreSQL 16 sebagai persistent dedup store. |
| `k6` | HTTP load testing opsional melalui Compose profile `k6`. |

Alur data:

1. Publisher mengirim single/batch event ke `POST /publish`.
2. Aggregator memvalidasi schema event dengan Pydantic.
3. Event valid dimasukkan ke Redis Streams.
4. Worker aggregator membaca stream melalui Redis consumer group.
5. Worker menjalankan transaksi database.
6. Insert event memakai `INSERT ... ON CONFLICT DO NOTHING`.
7. Jika insert berhasil, event dihitung sebagai unik.
8. Jika conflict, event dihitung sebagai duplicate.
9. Worker melakukan `XACK` setelah transaksi database sukses.

Jaringan Compose dibagi menjadi `edge` dan `backend`. Aggregator berada di `edge` agar dapat diakses dari `localhost:8080` untuk demo. Redis dan PostgreSQL hanya berada di `backend`, sehingga tidak membuka port ke host dan tetap menjadi layanan internal Compose.

## Model Event dan API

Format event minimal:

```json
{
  "topic": "auth.login",
  "event_id": "evt-001",
  "timestamp": "2026-01-01T00:00:00Z",
  "source": "publisher-1",
  "payload": {
    "level": "INFO",
    "message": "login success"
  }
}
```

Endpoint:

| Method | Endpoint | Fungsi |
|---|---|---|
| `POST` | `/publish` | Menerima single atau batch event. |
| `GET` | `/events?topic=...` | Menampilkan event unik yang telah diproses. |
| `GET` | `/stats` | Menampilkan `received`, `unique_processed`, `duplicate_dropped`, `duplicate_rate`, `topics`, dan uptime. |
| `GET` | `/audit` | Menampilkan audit log processed/duplicate. |
| `GET` | `/healthz` | Health check sederhana. |
| `GET` | `/readyz` | Readiness check database dan Redis. |
| `GET` | `/docs` | Swagger UI FastAPI. |

## Keputusan Desain

### Idempotency dan Deduplication

Identitas event ditentukan oleh pasangan `(topic, event_id)`. PostgreSQL memiliki unique constraint pada dua kolom tersebut. Ketika worker memproses event, insert dilakukan dengan `ON CONFLICT DO NOTHING`. Jika insert berhasil, event dianggap unik dan muncul di `/events`. Jika conflict, event dianggap duplicate, tidak dimasukkan lagi ke tabel event utama, tetapi tetap dicatat di audit log.

Pendekatan ini lebih kuat daripada menyimpan daftar event yang sudah diproses di memori aplikasi. Memori akan hilang saat container restart dan tidak aman jika worker bertambah. Dengan PostgreSQL dan named volume `pg_data`, riwayat dedup tetap ada walaupun container aggregator dibuat ulang.

### Transaksi dan Kontrol Konkurensi

Transaksi utama berada pada proses consumer. Dalam satu transaction boundary, sistem menaikkan counter `received`, mencoba insert event unik, menaikkan counter hasil (`unique_processed` atau `duplicate_dropped`), dan menulis audit log. Atomicity memastikan tidak ada update setengah jalan. Jika transaksi gagal, pesan Redis tidak di-ack sehingga dapat diproses ulang.

Isolation level PostgreSQL yang dipilih adalah `READ COMMITTED`. Correctness dedup tidak bergantung pada pola read-then-insert, melainkan pada unique constraint dan atomic upsert. Ini menghindari race condition ketika dua worker memproses event yang sama secara paralel. Counter statistik juga diperbarui dengan SQL increment `value = value + 1`, bukan read-modify-write di aplikasi, sehingga lost update dapat dihindari.

### Reliability, Retry, dan Ordering

Redis Streams memberi model at-least-once. Pesan baru di-ack hanya setelah transaksi database sukses. Jika worker crash sebelum ack, pesan tetap pending dan dapat diklaim ulang dengan `XAUTOCLAIM`. Karena consumer idempotent, pemrosesan ulang tidak membuat event unik ganda.

Sistem tidak menerapkan total ordering global karena log aggregator tidak membutuhkan konsensus urutan semua event lintas topic. Ordering praktis memakai timestamp dari producer dan `logical_seq` dari id database. Ini cukup untuk menampilkan event secara stabil sambil tetap menerima kemungkinan event out-of-order.

### Persistensi dan Observability

PostgreSQL memakai named volume `pg_data`, sedangkan Redis memakai `broker_data`. Data dedup tetap aman saat container aggregator dihapus atau dibuat ulang. Observability disediakan melalui `/stats`, `/audit`, `/healthz`, `/readyz`, Swagger UI, dan logging worker yang membedakan event `processed` dan `duplicate dropped`.

## Cara Menjalankan

Jalankan stack utama:

```powershell
docker compose up --build
```

Mode background:

```powershell
docker compose up --build -d aggregator
```

Akses aggregator:

```text
http://localhost:8080
```

Jalankan publisher 20.000 event:

```powershell
docker compose --profile load run --rm publisher
```

Jalankan K6 opsional:

```powershell
docker compose --profile k6 run --rm k6
```

Jalankan test:

```powershell
python -m pytest -q
```

## Hasil Pengujian

Unit/integration test lokal:

```text
20 passed in 12.65s
```

Cakupan test:

- Validasi schema event.
- Single publish dan batch publish.
- Dedup event duplikat.
- Event id sama pada topic berbeda.
- Persistence dedup state setelah storage dibuka ulang.
- Konkurensi 50 proses pada event yang sama.
- Stress kecil 300 event.
- Konsistensi `/stats` dan `/events`.

Hasil uji konkurensi inti: test `test_concurrent_duplicate_processing_inserts_once` memproses event yang sama 50 kali secara concurrent. Hasilnya hanya satu operasi yang berhasil sebagai insert unik, sedangkan sisanya masuk duplicate. Ini membuktikan bahwa race condition dedup dicegah oleh constraint database, bukan oleh timing aplikasi.

## Analisis Performa dan Metrik

Benchmark utama:

```powershell
docker compose --profile load run --rm `
  -e TOTAL_EVENTS=20000 `
  -e DUPLICATE_RATE=0.30 `
  -e BATCH_SIZE=500 `
  -e CONCURRENCY=4 `
  -e SOURCE=publisher-20k `
  -e SEED=publisher-20k `
  publisher
```

Ekspektasi konfigurasi:

| Metrik | Nilai |
|---|---:|
| Total event dikirim | 20.000 |
| Duplicate rate target | 30 persen |
| Expected unique | 14.000 |
| Expected duplicate | 6.000 |
| Batch size | 500 |
| Publisher concurrency | 4 |

Metrik benchmark yang digunakan:

| Metrik | Nilai/Sumber |
|---|---|
| Total event benchmark publisher | 20.000 event |
| Duplicate rate target publisher | 30 persen |
| Expected unique publisher | 14.000 event |
| Expected duplicate publisher | 6.000 event |
| Batch size publisher | 500 event/request |
| Publisher concurrency | 4 concurrent request |
| K6 default request rate | 4 iterasi/detik |
| K6 default batch size | 100 event/request |
| K6 default event rate target | 400 event/detik |
| K6 default duration | 1 menit |
| K6 latency threshold | `http_req_duration p(95) < 1000 ms` |
| Duplicate metric runtime | `duplicate_rate` dari `GET /stats` |
| Throughput runtime | `throughput_events_per_second` dari output publisher |
| Latency runtime | `http_req_duration` dari output K6 jika K6 dijalankan |

Catatan interpretasi: `received` adalah jumlah processing attempt yang dikonsumsi worker. Pada model at-least-once, nilai ini dapat sedikit lebih tinggi dari total event yang dikirim jika ada redelivery. Kebenaran dedup terutama dibuktikan oleh `unique_processed`, `duplicate_dropped`, dan fakta bahwa `/events` hanya berisi event unik.

## Keterkaitan Teori Bab 1-13

### T1 - Karakteristik Sistem Terdistribusi dan Trade-off Pub-Sub Aggregator

Sistem ini termasuk sistem terdistribusi karena terdiri dari beberapa komponen independen yang berjalan sebagai proses/container berbeda, berkomunikasi melalui jaringan lokal Compose, dan harus tampak sebagai satu layanan log aggregator. Karakteristik pentingnya adalah concurrency, partial failure, heterogeneity, dan kebutuhan koordinasi antar komponen. Publisher, broker, aggregator worker, dan storage dapat berjalan atau gagal secara terpisah. Ini sesuai dengan konsep sistem terdistribusi sebagai kumpulan komputer otonom yang berkoordinasi melalui message passing (Coulouris et al., 2012).

Trade-off utama arsitektur pub-sub adalah decoupling versus kompleksitas. Publisher tidak perlu tahu worker mana yang memproses event; ia hanya mengirim event ke aggregator/broker. Ini meningkatkan scalability dan fault tolerance karena worker dapat ditambah. Namun desain ini menerima konsekuensi asynchronous processing: event yang sudah diterima API belum tentu langsung muncul di `/events`. Selain itu delivery biasanya at-least-once, sehingga duplikasi harus dianggap normal. Karena itu rancangan memakai idempotent consumer dan dedup store persisten.

### T2 - Kapan Memilih Publish-Subscribe dibanding Client-Server

Publish-subscribe dipilih ketika producer dan consumer perlu dipisahkan dalam waktu, lokasi, dan jumlah. Pada model client-server biasa, client mengirim request ke server dan mengharapkan response langsung dari server yang sama. Model itu cocok untuk operasi sinkron sederhana. Namun log aggregator membutuhkan ingestion berkecepatan tinggi, toleransi terhadap lonjakan traffic, dan pemrosesan asynchronous. Publisher sebaiknya tidak menunggu semua proses dedup dan audit selesai sebelum request dianggap diterima.

Dengan pub-sub, aggregator dapat menerima event lalu memasukkannya ke broker. Worker kemudian memproses event secara paralel. Jika worker lambat, broker menjadi buffer. Jika ada duplikasi atau retry, storage tetap menjaga idempotency. Ini sejalan dengan pembahasan arsitektur terdistribusi bahwa pemisahan komponen dapat meningkatkan scalability dan evolvability, tetapi membutuhkan protokol komunikasi dan koordinasi yang jelas (Coulouris et al., 2012). Dalam proyek ini, Redis Streams menjadi mekanisme komunikasi asynchronous internal, sedangkan FastAPI tetap menyediakan interface HTTP sederhana untuk publisher dan user demo.

### T3 - At-Least-Once vs Exactly-Once Delivery dan Peran Idempotent Consumer

At-least-once delivery berarti setiap pesan akan dikirim minimal satu kali, tetapi mungkin dikirim lebih dari sekali. Exactly-once delivery berarti efek pemrosesan terjadi tepat satu kali. Dalam sistem terdistribusi nyata, exactly-once sulit dicapai secara end-to-end karena crash, retry, timeout, dan ketidakpastian status pesan dapat membuat producer atau broker mengirim ulang pesan. Coulouris et al. (2012) menjelaskan bahwa failure dan komunikasi tidak andal adalah persoalan mendasar dalam sistem terdistribusi.

Rancangan ini memilih at-least-once delivery dan membuat efeknya idempotent. Redis Streams menyimpan pesan, worker memprosesnya, lalu melakukan ack setelah transaksi database sukses. Jika worker crash sebelum ack, pesan dapat dikirim ulang. Duplikasi tersebut tidak merusak data karena consumer menggunakan `(topic, event_id)` sebagai kunci dedup. Jika event yang sama diproses ulang, insert ke `processed_events` akan conflict dan diabaikan. Dengan begitu, delivery boleh terjadi lebih dari sekali, tetapi side effect penting hanya terjadi sekali.

### T4 - Skema Penamaan Topic dan Event ID

Topic dipakai sebagai namespace log, misalnya `auth.login`, `payments`, `inventory`, dan `system.metrics`. Format topic dibatasi pada huruf, angka, titik, garis bawah, titik dua, dan tanda hubung agar mudah dipakai sebagai label metrik serta aman untuk query. `event_id` adalah identifier unik di dalam satu topic. Constraint database menggunakan pasangan `(topic, event_id)`, bukan hanya `event_id`, sehingga dua domain berbeda boleh memakai id yang sama tanpa konflik.

Skema ini membantu dedup karena collision domain menjadi jelas. Publisher dapat memakai UUID, ULID, atau id deterministik dari sumber event. Dalam implementasi demo, publisher default memakai UUID v4. Untuk demo persistence, env `SEED` menghasilkan id deterministik agar event yang sama dapat dikirim ulang setelah container recreate. Bab naming dalam sistem terdistribusi menekankan bahwa nama harus dapat mengidentifikasi resource secara stabil dalam sistem yang komponennya terpisah (Coulouris et al., 2012). Di sini, nama stabilnya adalah kombinasi topic dan event id.

### T5 - Ordering Praktis

Sistem tidak memaksakan total ordering global untuk semua event. Total ordering lintas publisher dan lintas topic membutuhkan koordinasi tambahan yang mahal, misalnya sequencer global atau konsensus. Untuk log aggregator, kebutuhan utamanya adalah menampilkan event secara masuk akal dan mencegah duplikasi. Karena itu ordering praktis memakai dua data: timestamp dari event dan `logical_seq` dari id database saat event unik berhasil disimpan.

Timestamp membantu membaca urutan kejadian dari perspektif producer, tetapi clock antar mesin bisa berbeda. `logical_seq` membantu memberi urutan monotonic lokal di storage untuk event yang sudah diproses. Kombinasi ini memberi ordering yang stabil untuk tampilan `/events`, tetapi tidak diklaim sebagai causal ordering sempurna. Pembahasan waktu dan ordering pada sistem terdistribusi menunjukkan bahwa clock fisik memiliki keterbatasan, sehingga desain sering memakai logical ordering atau menerima ordering parsial sesuai kebutuhan aplikasi (Coulouris et al., 2012).

### T6 - Failure Modes dan Mitigasi

Failure mode utama adalah duplikasi event, crash worker, restart container, broker pending message, dan storage yang harus tetap konsisten. Publisher juga bisa melakukan retry ketika request gagal, sehingga event yang sama mungkin masuk lebih dari sekali. Worker aggregator bisa crash setelah membaca pesan tetapi sebelum ack. Dalam kondisi itu, Redis Streams menyimpan pesan sebagai pending. Implementasi memakai `XAUTOCLAIM` untuk mengambil ulang pesan stale agar dapat diproses worker lain.

Mitigasi paling penting adalah dedup store persisten. PostgreSQL menyimpan `processed_events` pada named volume `pg_data`, sehingga container recreate tidak menghapus riwayat dedup. Ack Redis dilakukan setelah transaksi database selesai. Jika worker crash sebelum ack, event akan diproses ulang, tetapi insert kedua akan conflict dan dihitung sebagai duplicate. Desain ini mengikuti prinsip fault tolerance bahwa sistem harus tetap benar meskipun sebagian komponen gagal, bukan mengasumsikan jaringan dan proses selalu sehat (Coulouris et al., 2012).

### T7 - Eventual Consistency pada Aggregator

Aggregator bersifat eventually consistent karena publish dan processing dipisahkan oleh queue. Setelah `POST /publish` berhasil, event sudah diterima dan dimasukkan ke Redis Streams, tetapi belum tentu langsung muncul di `/events`. Event baru terlihat setelah worker membaca stream dan transaksi database selesai. Keterlambatan ini adalah trade-off dari desain asynchronous. Keuntungannya, sistem lebih responsif saat menerima batch besar dan worker dapat memproses secara paralel.

Eventual consistency tetap aman karena operasi write dirancang idempotent. Jika event diproses ulang, database tidak menghasilkan record unik kedua. Jika ada beberapa worker, hanya satu yang berhasil insert untuk `(topic, event_id)` yang sama. Dengan kata lain, state akhir storage akan konvergen ke kumpulan event unik walaupun jalur menuju state itu berisi retry dan duplikasi. Coulouris et al. (2012) membahas bahwa konsistensi dalam sistem terdistribusi sering melibatkan trade-off antara ketersediaan, performa, dan kekuatan jaminan konsistensi. Rancangan ini memilih konsistensi akhir yang diperkuat oleh dedup transaksional.

### T8 - Desain Transaksi: ACID, Isolation, dan Lost Update

Transaksi utama berada pada fungsi pemrosesan event. Dalam satu transaksi, sistem menaikkan counter `received`, mencoba insert event unik, menaikkan counter `unique_processed` atau `duplicate_dropped`, dan menulis audit log. Atomicity memastikan perubahan ini tidak setengah jalan. Jika transaksi gagal, pesan Redis tidak di-ack sehingga bisa diproses ulang. Consistency dijaga oleh constraint unik `(topic, event_id)`. Durability diberikan oleh PostgreSQL dan named volume.

Isolation level yang dipakai adalah `READ COMMITTED` pada PostgreSQL. Level ini cukup karena konflik dedup tidak diselesaikan melalui read-then-write manual, melainkan melalui unique index dan `ON CONFLICT DO NOTHING`. Lost update pada counter dicegah dengan SQL increment atomik `value = value + 1`, bukan membaca nilai counter ke aplikasi lalu menulis ulang. Bab transaksi menekankan pentingnya ACID untuk menjaga correctness saat operasi concurrent terjadi (Coulouris et al., 2012). Dalam proyek ini, correctness terletak pada fakta bahwa event unik tidak dapat diproses dua kali walau banyak worker aktif.

### T9 - Kontrol Konkurensi: Locking, Unique Constraint, dan Idempotent Write Pattern

Kontrol konkurensi paling penting adalah unique constraint pada tabel `processed_events`. Ketika dua worker memproses event sama secara paralel, keduanya mencoba insert `(topic, event_id)` yang sama. Database mengizinkan hanya satu transaksi berhasil. Transaksi lain tidak merusak data; ia menerima conflict dan operasi insert diabaikan. Inilah idempotent write pattern: request yang sama dapat diulang tanpa menghasilkan side effect ganda.

Pendekatan ini lebih kuat daripada melakukan `SELECT` dahulu untuk mengecek apakah event sudah ada. Pada pola read-then-insert, dua worker bisa sama-sama membaca data belum ada lalu bersaing saat insert. Dengan unique constraint, mekanisme locking dan conflict detection didelegasikan ke database. Counter juga diperbarui secara atomik. Bab kontrol konkurensi menjelaskan masalah seperti lost update dan race condition saat transaksi berjalan bersamaan (Coulouris et al., 2012). Implementasi ini membuktikannya lewat test `test_concurrent_duplicate_processing_inserts_once`, yaitu 50 operasi concurrent hanya menghasilkan satu event unik.

### T10 - Orkestrasi Compose, Keamanan Lokal, Persistensi, dan Observability

Docker Compose mengorkestrasi aggregator, publisher, broker, storage, dan K6 opsional. Redis dan PostgreSQL berada di network `backend` yang bersifat internal dan tidak membuka port host. Aggregator expose port `8080` untuk demo lokal melalui network `edge`. Ini memenuhi batasan bahwa sistem berjalan pada jaringan lokal Compose tanpa layanan eksternal publik saat runtime. Healthcheck disediakan untuk Redis, PostgreSQL, dan aggregator `/readyz`.

Persistensi dilakukan dengan named volume `pg_data` untuk PostgreSQL dan `broker_data` untuk Redis AOF. Dengan demikian data tetap ada setelah container dihapus atau aggregator dibuat ulang. Observability diberikan melalui endpoint `/stats`, `/audit`, `/healthz`, `/readyz`, Swagger UI, dan logging worker yang membedakan event `processed` dan `duplicate dropped`. Bab sistem berbasis web, storage, dan koordinasi menekankan pentingnya pengelolaan resource, fault tolerance, dan monitoring dalam sistem terdistribusi (Coulouris et al., 2012). Compose membuat deployment lokal dapat direproduksi untuk demo dan pengujian.

## Kesimpulan

Sistem ini menunjukkan pola praktis untuk membangun aggregator terdistribusi yang menerima at-least-once delivery tetapi tetap menjaga konsistensi data. Kunci correctness adalah idempotent consumer, persistent dedup store, transaksi database, dan kontrol konkurensi berbasis unique constraint. Redis Streams memberi decoupling dan retry, sedangkan PostgreSQL menjadi sumber kebenaran untuk event unik, stats, dan audit.

## Referensi

Coulouris, G., Dollimore, J., Kindberg, T., & Blair, G. (2012). *Distributed systems: Concepts and design* (5th ed.). Addison-Wesley.
