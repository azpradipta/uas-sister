# Skrip Demo Lengkap UAS

File ini dibuat supaya demo bisa diikuti dari awal sampai akhir. Formatnya:

- "Bacakan" = narasi yang kamu ucapkan di video.
- "Lakukan" = aksi yang kamu lakukan di terminal/browser.
- "Copas" = command PowerShell yang bisa langsung dicopy.
- "Tunjukkan" = bagian output yang perlu disorot.

Durasi target: 30 sampai 40 menit jika semua narasi tambahan dibacakan. Kalau waktu sudah cukup, bagian "Bacakan tambahan" boleh dipersingkat.

Tips membacakan:

- Baca pelan, jangan terburu-buru saat menjelaskan konsep transaksi dan dedup.
- Setelah menjalankan command, tunggu output muncul lalu jelaskan arti output-nya.
- Kalau ada angka yang berbeda dari contoh, tidak apa-apa. Jelaskan berdasarkan pola: `unique_processed` untuk event unik, `duplicate_dropped` untuk event duplikat, dan `/events` untuk data unik final.
- Kata kunci yang perlu sering disebut: at-least-once delivery, idempotent consumer, persistent dedup store, transaction, unique constraint, race condition, dan Docker Compose local network.

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

Bacakan tambahan sebelum mulai record, jika ingin:

> Sebelum merekam, saya memastikan Docker Desktop aktif, terminal memakai PowerShell, dan saya berada di folder project yang benar. Saya juga memastikan port `8080` tidak dipakai aplikasi lain, karena aggregator akan berjalan di `localhost:8080`. Dependency Python dipakai untuk menjalankan test lokal, sedangkan sistem utama tetap dijalankan melalui Docker Compose.

> Kalau ingin demo dari kondisi benar-benar kosong, saya bisa memakai `docker compose down -v`. Tetapi command itu menghapus volume, jadi hanya dipakai saat rehearsal bersih. Untuk demo persistence, volume justru harus dipertahankan agar terlihat bahwa data dedup tidak hilang saat container dibuat ulang.

## 0:00 - 1:30 Pembukaan

Bacakan:

> Halo, saya [nama], pada video ini saya mendemokan proyek UAS Sistem Terdistribusi dengan tema Pub-Sub Log Aggregator Terdistribusi. Sistem ini dibuat dengan Python, FastAPI, Redis Streams, PostgreSQL, dan Docker Compose. Fokus utama implementasi ini adalah idempotent consumer, deduplication persisten, transaksi database, dan kontrol konkurensi agar event yang sama tidak diproses dua kali walaupun dikirim berulang atau diproses oleh beberapa worker paralel.

> Demo ini akan menunjukkan arsitektur multi-service, cara menjalankan Docker Compose, publish event normal dan duplikat, statistik, audit log, uji concurrency melalui publisher, persistence setelah container recreate, serta test suite.

Bacakan tambahan:

> Masalah utama yang ingin diselesaikan adalah masalah umum pada sistem terdistribusi: pesan bisa datang lebih dari sekali. Misalnya publisher melakukan retry karena timeout, worker crash sebelum ack, atau broker mengirim ulang pesan yang belum dikonfirmasi. Karena itu sistem tidak mengasumsikan bahwa setiap event hanya datang sekali.

> Pendekatan yang saya pakai adalah menerima model at-least-once delivery, lalu membuat consumer bersifat idempotent. Artinya, walaupun event yang sama diterima berkali-kali, efek akhirnya tetap sama seperti diproses satu kali. Di project ini, efek akhirnya adalah satu event unik tersimpan di PostgreSQL berdasarkan pasangan `(topic, event_id)`.

## 1:30 - 4:00 Jelaskan Struktur Project

Lakukan:

Tampilkan daftar file utama.

Copas:

```powershell
Get-ChildItem
```

Bacakan:

> Struktur project terdiri dari folder `aggregator`, `publisher`, `tests`, `docker-compose.yml`, `README.md`, `report.md`, dan file panduan demo. Folder `aggregator` berisi API FastAPI, consumer worker, koneksi Redis Streams, dan storage transaction logic. Folder `publisher` berisi simulator event yang dapat mengirim event batch dengan duplicate rate tertentu. Folder `tests` berisi 20 test untuk validasi schema, deduplication, persistence, concurrency, stats, dan API.

Bacakan tambahan:

> Struktur ini sengaja dipisah mengikuti konsep separation of concerns. Aggregator fokus pada API dan pemrosesan event. Publisher fokus sebagai producer atau generator traffic. Redis berperan sebagai broker, dan PostgreSQL menjadi sumber kebenaran untuk data yang sudah diproses.

> Dengan pemisahan ini, kita bisa menjelaskan sistem sebagai beberapa service yang bekerja sama, bukan satu program monolitik. Ini sesuai dengan karakteristik sistem terdistribusi, yaitu ada beberapa komponen yang berjalan independen, berkomunikasi lewat jaringan, dan tetap harus menjaga konsistensi data.

Tampilkan file penting:

```powershell
Get-ChildItem .\aggregator\app
Get-ChildItem .\publisher
Get-ChildItem .\tests
```

Bacakan:

> File paling penting untuk correctness adalah `database.py`, karena di sana ada transaksi dan unique constraint. `consumer.py` berisi worker paralel yang membaca Redis Streams. `queue.py` berisi operasi Redis Streams, sedangkan `main.py` berisi endpoint API.

Bacakan tambahan:

> `models.py` juga penting karena mendefinisikan schema event. Validasi schema mencegah event yang tidak sesuai format masuk ke sistem. Jadi sebelum masuk ke Redis Streams, event sudah dicek minimal memiliki `topic`, `event_id`, `timestamp`, `source`, dan `payload`.

> Folder `tests` menunjukkan bahwa fitur inti tidak hanya didemokan manual, tetapi juga diuji otomatis. Ini penting karena race condition dan idempotency sering terlihat benar secara manual, tetapi baru terbukti kuat kalau diuji dengan skenario concurrent.

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

Bacakan tambahan:

> Alasan memakai publish-subscribe adalah agar producer tidak terikat langsung dengan proses penyimpanan ke database. Publisher cukup mengirim event ke API, lalu aggregator memasukkan event ke broker. Setelah itu worker dapat memproses secara asynchronous. Ini membuat sistem lebih tahan terhadap lonjakan traffic dibanding semua pekerjaan dilakukan langsung di request HTTP.

> Redis Streams dipakai sebagai broker karena mendukung stream data, consumer group, pending message, dan ack. Dengan consumer group, beberapa worker bisa membaca stream secara paralel. Dengan ack, sistem tahu pesan mana yang sudah selesai diproses.

> PostgreSQL dipakai karena requirement UAS menekankan transaksi dan kontrol konkurensi. Database relasional cocok untuk menunjukkan ACID transaction, isolation level, unique constraint, dan atomic upsert. Jadi deduplication tidak hanya dilakukan di kode Python, tetapi dijamin oleh database.

> Network Compose juga penting untuk bagian keamanan dan orkestrasi. Redis dan PostgreSQL tidak diekspos ke luar host, sehingga akses ke storage dan broker hanya terjadi antar-service di jaringan lokal Compose. Ini sesuai ketentuan bahwa sistem tidak memakai layanan eksternal publik.

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

Bacakan tambahan:

> `docker compose up --build -d aggregator` akan membangun image aplikasi, menarik image Redis dan PostgreSQL jika belum ada, lalu menjalankan service di background. Aggregator memiliki dependency ke broker dan storage, sehingga Compose menunggu healthcheck Redis dan PostgreSQL sebelum aggregator aktif.

> Healthcheck bukan hanya kosmetik. Dalam sistem terdistribusi, urutan startup service bisa berbeda-beda. Aggregator tidak boleh dianggap siap hanya karena container hidup; aggregator baru siap jika bisa mengakses Redis dan PostgreSQL.

Tunjukkan readiness:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8080/readyz'
```

Bacakan:

> Endpoint `/readyz` memastikan aggregator bisa terhubung ke database dan Redis. Kalau statusnya `ready`, berarti service sudah siap menerima event.

Bacakan tambahan:

> Saya membedakan readiness dan health. Health bisa berarti aplikasi masih hidup, sedangkan readiness berarti aplikasi siap melayani traffic karena dependency pentingnya tersedia. Untuk aggregator ini, dependency pentingnya adalah database dan broker.

Tampilkan stats awal:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8080/stats' | ConvertTo-Json -Depth 10
```

Bacakan:

> Endpoint `/stats` menampilkan jumlah processing attempt yang diterima worker, jumlah event unik yang berhasil diproses, jumlah duplicate yang dibuang, duplicate rate, daftar topic, dan uptime.

Bacakan tambahan:

> `received` di sini berarti jumlah attempt yang sudah dikonsumsi worker, bukan semata-mata jumlah request HTTP. Pada sistem at-least-once, angka ini bisa sedikit lebih besar dari jumlah event yang dikirim jika ada redelivery. Yang menjadi bukti dedup utama adalah `unique_processed`, `duplicate_dropped`, dan isi `/events`.

## 10:00 - 12:00 Buka Browser untuk Swagger UI

Lakukan:

Buka Swagger UI FastAPI di browser.

Copas:

```powershell
Start-Process 'http://localhost:8080/docs'
```

Bacakan:

> Saya buka Swagger UI dari FastAPI di browser. Ini menunjukkan bahwa aggregator benar-benar berjalan sebagai web API di `localhost:8080`. Di sini terlihat endpoint utama: `POST /publish`, `GET /events`, `GET /stats`, `GET /audit`, `/healthz`, dan `/readyz`.

Bacakan tambahan:

> Swagger UI juga membantu menunjukkan kontrak API. Dosen atau pengguna bisa melihat endpoint apa saja yang tersedia tanpa membaca kode. Ini bagian dari sistem berbasis web, karena API tidak hanya berjalan, tetapi juga terdokumentasi secara otomatis.

> `POST /publish` adalah pintu masuk event. `GET /events` adalah cara melihat event unik yang sudah diproses. `GET /stats` memberi metrik ringkas. `GET /audit` memberi jejak apakah event diproses atau dianggap duplikat. `/healthz` dan `/readyz` mendukung observability dan deployment.

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

Bacakan tambahan:

> Browser saya gunakan untuk membuktikan bahwa API dapat diakses seperti web service biasa. PowerShell saya gunakan untuk bagian yang lebih terukur, karena command-nya bisa diulang dan output JSON-nya bisa dibandingkan sebelum dan sesudah event dikirim.

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

Bacakan tambahan:

> Model event minimal terdiri dari `topic`, `event_id`, `timestamp`, `source`, dan `payload`. `topic` berfungsi sebagai kategori atau channel log. `event_id` adalah identitas unik event di dalam topic. `timestamp` memberi waktu kejadian dari producer. `source` menunjukkan asal event, dan `payload` berisi data log fleksibel.

> Di sini saya sengaja memakai event manual agar alurnya mudah dipahami sebelum masuk ke load test. Kalau event manual saja sudah terlihat di `/events`, berarti jalur dari API ke Redis Streams, dari worker ke PostgreSQL, dan dari PostgreSQL ke endpoint query sudah berjalan.

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

Bacakan tambahan:

> Perlu diperhatikan bahwa `/publish` dan `/events` tidak selalu sinkron secara instan. `/publish` menerima event dan memasukkannya ke queue, sementara `/events` menampilkan hasil setelah worker memproses. Ini contoh eventual consistency dalam sistem terdistribusi.

Cek stats:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8080/stats' | ConvertTo-Json -Depth 10
```

Bacakan:

> Setelah satu event unik, `received` naik, `unique_processed` naik, dan `duplicate_dropped` masih nol atau belum bertambah.

Bacakan tambahan:

> Kalau sebelumnya database sudah berisi data dari rehearsal, angka awal mungkin tidak nol. Yang penting adalah pola perubahannya. Setelah event unik baru dikirim, `unique_processed` bertambah satu, dan topic `auth.login` muncul atau bertambah jumlahnya.

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

Bacakan tambahan:

> Ini inti dari perbedaan delivery dan processing effect. Delivery boleh terjadi lebih dari sekali, tetapi side effect ke database harus tepat satu kali untuk event yang sama. Karena itu saya tidak mengklaim broker memberikan exactly-once delivery. Yang saya pastikan adalah exactly-once effect untuk penyimpanan event unik melalui idempotent consumer.

> Dalam sistem nyata, duplikasi tidak selalu berasal dari kesalahan. Duplikasi bisa terjadi karena retry yang justru dibutuhkan untuk reliability. Jadi sistem yang baik harus aman terhadap retry. Di sini, retry aman karena event yang sama hanya menambah counter duplicate, bukan membuat data unik baru.

Cek audit:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8080/audit?limit=5' | ConvertTo-Json -Depth 10
```

Bacakan:

> Audit log menunjukkan dua status: event pertama `processed`, dan event kedua `duplicate`. Detail duplicate menjelaskan bahwa event diabaikan oleh unique constraint.

Bacakan tambahan:

> Audit log membantu observability. Tanpa audit, kita hanya melihat angka statistik. Dengan audit, kita bisa melihat contoh konkret event mana yang diproses dan event mana yang dianggap duplikat. Ini berguna saat debugging dan saat membuktikan ke evaluator bahwa dedup benar-benar terjadi.

Tampilkan event unik lagi:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8080/events?topic=auth.login&limit=10' | ConvertTo-Json -Depth 10
```

Bacakan:

> Walaupun event dengan id yang sama dikirim dua kali, daftar `/events` tetap hanya menyimpan satu event unik untuk topic dan event id tersebut.

Bacakan tambahan:

> Ini membedakan tabel utama dan audit. Tabel utama `processed_events` hanya menyimpan event unik. Audit boleh menyimpan catatan duplicate karena audit adalah riwayat attempt, bukan sumber data unik. Dengan begitu, sistem tetap punya data bersih sekaligus jejak observability.

Opsional, buka hasil event di browser:

```powershell
Start-Process 'http://localhost:8080/events?topic=auth.login&limit=10'
```

Bacakan:

> Di browser juga terlihat bahwa endpoint `/events` hanya mengembalikan event unik yang sudah diproses.

Bacakan tambahan:

> Kalau output di browser hanya menampilkan satu record untuk `manual-demo-1`, itu adalah bukti visual bahwa payload duplicate tidak mengganti atau menggandakan event utama. Record pertama tetap menjadi data unik yang disimpan.

## 18:00 - 22:00 Jelaskan Transaksi dan Kontrol Konkurensi dari Kode

Lakukan:

Tampilkan bagian unique constraint.

Copas:

```powershell
Select-String -Path .\aggregator\app\database.py -Pattern 'UniqueConstraint|uq_processed_topic_event_id' -Context 3,3
```

Bacakan:

> Deduplication utama dilakukan oleh unique constraint `(topic, event_id)`. Artinya database tidak mengizinkan dua record dengan topic dan event id yang sama. Ini lebih aman daripada hanya mengecek duplikat di memori aplikasi, karena memori akan hilang saat container restart.

Bacakan tambahan:

> Unique constraint juga aman terhadap concurrency. Kalau dua worker hampir bersamaan mencoba memasukkan event yang sama, keduanya tidak bisa sama-sama berhasil. Database akan mengizinkan satu transaksi insert, sedangkan transaksi lain akan masuk jalur conflict.

> Kalau dedup hanya dilakukan dengan struktur data Python seperti set atau dictionary, dedup akan hilang ketika process restart. Selain itu, beberapa worker atau beberapa instance aggregator bisa memiliki memori berbeda. Karena itu dedup harus dipusatkan di storage yang persisten.

Tampilkan bagian transaksi process_event:

```powershell
Select-String -Path .\aggregator\app\database.py -Pattern 'async def process_event|on_conflict_do_nothing|unique_processed|duplicate_dropped' -Context 3,5
```

Bacakan:

> Pada fungsi `process_event`, worker membuka transaksi database. Di dalam transaksi ini, counter `received` dinaikkan, lalu sistem mencoba insert event ke tabel `processed_events`. Insert memakai `ON CONFLICT DO NOTHING`, sehingga kalau event sudah ada, database tidak membuat baris baru. Setelah itu sistem menaikkan counter `unique_processed` atau `duplicate_dropped`, lalu menulis audit log.

> Isolation level PostgreSQL yang dipakai adalah `READ COMMITTED`. Untuk kasus ini, correctness tidak hanya bergantung pada isolation level, tetapi pada unique constraint dan atomic upsert. Jadi ketika dua worker memproses event yang sama secara paralel, database menjadi arbiter: hanya satu insert yang berhasil.

Bacakan tambahan:

> Secara ACID, atomicity berarti update counter, insert event, dan audit log berada dalam satu transaction boundary. Kalau transaksi gagal, perubahan tidak disimpan setengah-setengah. Consistency dijaga oleh constraint unik. Isolation mencegah transaksi saling mengganggu secara berbahaya, dan durability diberikan oleh PostgreSQL serta volume persisten.

> Pola yang sengaja dihindari adalah read-then-insert biasa, misalnya aplikasi melakukan SELECT dulu untuk mengecek event ada atau tidak, lalu INSERT. Pola seperti itu rentan race condition karena dua worker bisa sama-sama membaca bahwa event belum ada. Dengan `INSERT ... ON CONFLICT DO NOTHING`, pengecekan dan penulisan dilakukan secara atomik oleh database.

> Counter juga diperbarui dengan operasi SQL `value = value + 1`, bukan dibaca ke aplikasi lalu ditulis ulang. Ini menghindari lost update ketika banyak worker menaikkan counter pada saat bersamaan.

Tampilkan worker ack:

```powershell
Select-String -Path .\aggregator\app\consumer.py -Pattern 'claim_stale|process_event|ack' -Context 2,4
```

Bacakan:

> Worker membaca pesan dari Redis Streams. Pesan baru di-ack setelah `process_event` selesai. Jika worker crash sebelum ack, pesan masih bisa diklaim ulang oleh worker lain. Karena consumer idempotent, pemrosesan ulang tidak menyebabkan side effect ganda.

Bacakan tambahan:

> Urutan ack ini penting. Kalau pesan di-ack sebelum database commit, lalu worker crash, event bisa hilang karena broker menganggap pesan sudah selesai padahal database belum menyimpan. Dengan ack setelah transaksi sukses, sistem memilih kemungkinan redelivery daripada kehilangan data. Redelivery aman karena dedup sudah idempotent.

> `claim_stale` dipakai untuk mengambil pesan pending yang terlalu lama tidak di-ack. Ini mensimulasikan mekanisme recovery ketika worker mati di tengah jalan. Jadi reliability sistem tidak hanya berdasarkan happy path, tetapi juga memperhitungkan crash recovery.

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

Bacakan tambahan:

> Pada load test, publisher memakai batch agar pengiriman lebih efisien. `CONCURRENCY=4` berarti ada beberapa request batch yang bisa berjalan bersamaan. Ini memberi tekanan ke aggregator dan queue, sehingga worker paralel benar-benar dipakai.

> `SEED` membuat event yang dihasilkan deterministic. Ini berguna untuk demo persistence karena run kedua dengan seed yang sama akan menghasilkan event id yang sama. Tanpa seed, publisher akan menghasilkan UUID baru sehingga sulit membuktikan replay event yang sama.

> Untuk video, saya bisa memakai 3000 event agar demo tidak terlalu lama. Untuk laporan final, requirement meminta minimal 20.000 event dengan minimal 30 persen duplikasi, jadi command 20.000 event perlu dijalankan dan metriknya dicatat.

Tunggu worker mengejar queue:

```powershell
for ($i = 1; $i -le 10; $i++) {
  Invoke-RestMethod -Uri 'http://localhost:8080/stats' | ConvertTo-Json -Depth 10
  Start-Sleep -Seconds 5
}
```

Bacakan:

> Karena sistem asynchronous, stats tidak harus langsung selesai pada detik yang sama dengan publisher. Worker akan terus membaca queue sampai semua event diproses. Kebenaran utama dilihat dari `unique_processed`, `duplicate_dropped`, dan isi `/events`.

Bacakan tambahan:

> Kalau stats bergerak bertahap, itu justru menunjukkan arsitektur queue sedang bekerja. Publisher sudah selesai mengirim, tetapi worker masih mengonsumsi backlog. Ini adalah salah satu manfaat broker: producer bisa selesai lebih cepat, sementara consumer memproses sesuai kapasitasnya.

> Dalam membaca hasil, saya membandingkan `expected_unique` dan `expected_duplicates` dari output publisher dengan angka pada `/stats`. Jika sebelumnya sudah ada data manual, angka total akan lebih besar, jadi yang dibandingkan adalah selisih atau pola kenaikannya.

Tampilkan log aggregator:

```powershell
docker compose logs aggregator --tail=50
```

Bacakan:

> Log menunjukkan event yang diproses dan duplicate yang di-drop. Ini bagian observability dari sistem.

Bacakan tambahan:

> Observability penting karena distributed system sulit dianalisis hanya dari satu output. Stats memberi angka agregat, audit memberi jejak per event, dan logs memberi informasi aktivitas worker. Ketiganya membantu memastikan sistem tidak hanya berjalan, tetapi juga bisa diamati.

## 26:00 - 30:00 Persistence Setelah Container Recreate

Bacakan:

> Sekarang saya membuktikan bahwa dedup store persisten. Saya akan mengirim event deterministic dengan `SEED`, lalu recreate container aggregator. Setelah itu saya kirim event yang sama lagi. Jika storage persisten bekerja, run kedua tidak akan menambah unique event untuk set yang sama.

Bacakan tambahan:

> Bagian ini penting karena dedup yang hanya ada di memori tidak cukup untuk sistem terdistribusi. Container bisa mati, dibuat ulang, atau dipindah. Kalau setelah restart sistem lupa event yang sudah diproses, maka duplicate lama bisa masuk lagi sebagai event baru. Karena itu dedup store harus durable.

> Dalam Compose, durability ditunjukkan dengan named volume PostgreSQL. Recreate aggregator hanya mengganti container aplikasi, bukan menghapus volume database. Jadi state dedup tetap ada.

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

Bacakan tambahan:

> Ini juga menunjukkan crash tolerance dari sisi aplikasi. Aggregator bisa dibuat ulang tanpa kehilangan riwayat event yang sudah diproses. Selama PostgreSQL volume tetap ada, unique constraint masih memiliki data pembanding untuk menolak event lama yang dikirim ulang.

> Kalau ada sedikit perbedaan angka karena redelivery, itu masih sesuai dengan model at-least-once. Yang penting adalah tidak ada duplikasi pada tabel event unik. Dengan kata lain, attempt boleh bertambah, tetapi state final tetap konsisten.

## 30:00 - 33:00 Test Suite

Lakukan:

Jalankan test.

Copas:

```powershell
python -m pytest -q
```

Bacakan:

> Test suite berisi 20 test. Cakupannya meliputi validasi schema event, single dan batch publish, dedup event duplikat, event id sama pada topic berbeda, persistence dedup state setelah storage dibuka ulang, concurrency 50 proses untuk event yang sama, stress kecil 300 event, dan konsistensi endpoint stats.

Bacakan tambahan:

> Test concurrency adalah salah satu bukti paling penting. Dalam test tersebut, event yang sama diproses 50 kali secara concurrent, tetapi hasilnya hanya satu insert unik dan sisanya duplicate. Ini membuktikan bahwa race condition pada dedup tidak diselesaikan dengan timing kebetulan, tetapi oleh constraint database.

> Test lokal memakai SQLite sementara agar bisa dijalankan cepat tanpa Docker, tetapi pola yang diuji sama: unique constraint, transaksi, idempotent insert, dan counter. Saat sistem dijalankan melalui Compose, backend storage yang dipakai adalah PostgreSQL.

> Dengan 20 test, jumlahnya masih sesuai requirement 12 sampai 20 test. Jadi test suite memenuhi batas kuantitas dan juga mencakup fitur inti yang dinilai.

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

Bacakan tambahan:

> Trade-off desain yang saya ambil adalah tidak memaksakan exactly-once delivery di broker. Exactly-once end-to-end sulit dan mahal di sistem terdistribusi karena crash dan retry dapat terjadi di banyak titik. Sebagai gantinya, saya memilih at-least-once delivery dengan idempotent consumer. Ini lebih realistis dan tetap menjaga correctness data.

> Untuk ordering, sistem tidak membutuhkan total ordering global. Log ditampilkan berdasarkan timestamp event dan logical sequence dari database. Ini cukup untuk aggregator karena fokusnya adalah mengumpulkan log unik per topic, bukan menjalankan konsensus urutan global antar semua producer.

> Untuk consistency, sistem bersifat eventually consistent. Setelah publish berhasil, event belum tentu langsung muncul di `/events`, tetapi worker akan memproses queue sampai database mencapai state akhir yang benar. Dedup dan transaksi memastikan state akhir tersebut konsisten.

> Untuk concurrency control, bagian paling kuat adalah kombinasi unique constraint dan `ON CONFLICT DO NOTHING`. Ini adalah idempotent write pattern. Dengan pola ini, request yang sama bisa diulang tanpa menyebabkan side effect ganda.

## 36:00 - 37:00 Penutup

Bacakan:

> Kesimpulannya, sistem ini menerima kenyataan bahwa distributed messaging sering bersifat at-least-once. Daripada memaksa exactly-once delivery yang sulit, sistem membuat consumer idempotent. Dengan key `(topic, event_id)`, unique constraint, transaksi database, dan dedup store persisten, event yang sama boleh datang berkali-kali tetapi efek pemrosesan unik hanya terjadi sekali.

> Demo ini sudah menunjukkan API publish, event unik, duplicate dropped, stats, audit log, worker paralel, Docker Compose, persistence setelah recreate, dan test suite.

Bacakan tambahan:

> Jadi kontribusi utama project ini bukan hanya membuat API log sederhana, tetapi menunjukkan bagaimana prinsip sistem terdistribusi dipakai untuk menjaga correctness. Ada asynchronous messaging, retry tolerance, durable storage, transaction boundary, concurrency control, dan observability.

> Dengan desain ini, sistem tetap aman saat event duplikat, saat worker paralel, dan saat aggregator dibuat ulang. Inilah inti dari idempotent consumer pada sistem pub-sub terdistribusi.

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

Bacakan tambahan kalau bagian checklist ikut direkam:

> Setelah video selesai, bagian yang perlu saya lengkapi di laporan adalah identitas, link GitHub, link video YouTube, dan metrik final dari load test 20.000 event. Metrik ini penting karena requirement meminta bukti performa dan duplicate rate.

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

Bacakan tambahan kalau terjadi error saat demo:

> Jika ada error saat demo, saya akan menunjukkan troubleshooting secara transparan. Untuk sistem terdistribusi, melihat logs dan healthcheck adalah bagian normal dari operasional. Command `docker compose ps`, `docker compose logs`, `/readyz`, dan `/stats` membantu mengetahui apakah masalah ada di aggregator, broker, storage, atau hanya worker yang masih mengejar queue.
