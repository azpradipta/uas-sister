# Laporan UAS Sistem Terdistribusi

Judul: Pub-Sub Log Aggregator Terdistribusi dengan Idempotent Consumer, Deduplication, dan Transaksi/Kontrol Konkurensi

Nama: [Isi nama]

NIM: [Isi NIM]

Link repository: [Isi link GitHub]

Link video demo: [Isi link YouTube unlisted/public]

## Ringkasan Sistem

Sistem yang dibangun adalah log aggregator berbasis publish-subscribe. Publisher mengirim event JSON ke aggregator melalui endpoint `POST /publish`. Aggregator tidak langsung memproses event di request thread, tetapi memasukkannya ke Redis Streams. Beberapa worker internal aggregator membaca stream melalui consumer group, lalu menyimpan event unik ke PostgreSQL. Deduplication dilakukan secara persisten dengan unique constraint `(topic, event_id)` pada tabel `processed_events`.

Desain ini sengaja menerima model at-least-once delivery. Artinya event boleh muncul lebih dari sekali karena retry, duplikasi publisher, atau recovery setelah crash. Konsistensi dijaga oleh idempotent consumer: event dengan `(topic, event_id)` yang sama hanya menghasilkan satu record unik. Semua update penting dalam proses consumer berada dalam satu transaksi database: counter `received`, insert event unik, counter `unique_processed` atau `duplicate_dropped`, dan audit log.

## Arsitektur Implementasi

Komponen Compose:

- `aggregator`: FastAPI API dan multi-worker consumer.
- `publisher`: generator event dengan duplikasi dan mode deterministic `SEED`.
- `broker`: Redis Streams sebagai broker internal.
- `storage`: PostgreSQL 16 sebagai dedup store persisten.

Alur data:

1. Publisher mengirim event single/batch ke `POST /publish`.
2. Aggregator memvalidasi schema Pydantic.
3. Event valid dimasukkan ke Redis Streams.
4. Worker aggregator membaca stream secara paralel.
5. Worker menjalankan transaksi database.
6. `INSERT ... ON CONFLICT DO NOTHING` menentukan apakah event unik atau duplikat.
7. Worker melakukan `XACK` setelah transaksi database sukses.

## Keputusan Desain

### Idempotency dan Deduplication

Kunci idempotency adalah pasangan `(topic, event_id)`. Database memiliki constraint unik pada dua kolom tersebut. Ketika worker mencoba memproses event, query insert memakai `ON CONFLICT DO NOTHING`. Jika insert berhasil, event dianggap unik. Jika terjadi conflict, event dianggap duplikat dan hanya dicatat pada audit log serta counter `duplicate_dropped`.

Keuntungan pendekatan ini adalah dedup tidak bergantung pada memori worker. Jika container aggregator dihapus atau dibuat ulang, PostgreSQL tetap menyimpan riwayat event unik pada named volume `pg_data`.

### Transaksi dan Konkurensi

Storage Compose memakai PostgreSQL dengan isolation level `READ COMMITTED`. Race condition utama terjadi ketika dua worker memproses event dengan `(topic, event_id)` yang sama secara bersamaan. `READ COMMITTED` saja belum cukup jika logika dedup dilakukan dengan pola read-then-insert biasa, karena dua transaksi bisa membaca "belum ada" pada waktu berdekatan. Karena itu sistem memakai unique constraint dan atomic insert. Dengan `INSERT ... ON CONFLICT DO NOTHING`, database menjadi arbiter konkurensi.

Counter statistik diperbarui dengan SQL `value = value + 1`, bukan read-modify-write di aplikasi. Ini menghindari lost update ketika banyak worker menaikkan counter bersamaan.

### Reliability dan Ordering

Redis Streams memberi model at-least-once. Pesan baru hanya di-ack setelah transaksi database selesai. Jika worker crash sebelum ack, pesan tetap pending dan dapat diklaim ulang dengan `XAUTOCLAIM`. Karena event bisa diproses ulang, idempotency di database menjadi bagian penting dari reliability.

Ordering tidak memakai total ordering global. Sistem menampilkan event berdasarkan `timestamp` dari producer dan `logical_seq` dari id database. Ini cukup untuk log aggregator karena yang penting adalah dedup dan pencarian per topic, bukan konsensus urutan global semua topic.

## Hasil Pengujian

Unit/integration test lokal:

```text
20 passed in 20.50s
```

Cakupan test:

- Validasi schema event.
- Single dan batch publish.
- Dedup event duplikat.
- Event id sama pada topic berbeda.
- Persistence dedup state setelah storage dibuka ulang.
- Konkurensi 50 proses pada event yang sama.
- Stress kecil 300 event dengan duplikasi.
- Konsistensi stats dan filter events.

Benchmark Compose untuk laporan final:

```powershell
docker compose up --build -d aggregator
docker compose --profile load run --rm publisher
curl.exe http://localhost:8080/stats
```

Konfigurasi default publisher mengirim 20.000 event dengan duplicate rate 0,30. Ekspektasi event unik sekitar 14.000 dan duplicate sekitar 6.000. Catat throughput dari output publisher dan salin stats akhir dari `/stats` untuk laporan final.

Catatan interpretasi metrik: `received` adalah jumlah processing attempt di worker. Karena sistem memakai at-least-once delivery, redelivery dapat membuat `received` dan `duplicate_dropped` sedikit lebih tinggi dari jumlah event yang dikirim. Kebenaran dedup utama dibuktikan oleh `unique_processed` dan data unik pada `/events`.

## T1 - Karakteristik Sistem Terdistribusi dan Trade-off Pub-Sub Aggregator

Sistem ini termasuk sistem terdistribusi karena terdiri dari beberapa komponen independen yang berjalan sebagai proses/container berbeda, berkomunikasi melalui jaringan lokal Compose, dan harus tampak sebagai satu layanan log aggregator. Karakteristik pentingnya adalah concurrency, partial failure, heterogeneity, dan kebutuhan koordinasi antar komponen. Publisher, broker, aggregator worker, dan storage dapat berjalan atau gagal secara terpisah. Ini sesuai dengan konsep sistem terdistribusi sebagai kumpulan komputer otonom yang berkoordinasi melalui message passing (Coulouris et al., 2012).

Trade-off utama arsitektur pub-sub adalah decoupling versus kompleksitas. Publisher tidak perlu tahu worker mana yang memproses event; ia hanya mengirim event ke aggregator/broker. Ini meningkatkan scalability dan fault tolerance, karena worker dapat ditambah. Namun desain ini menerima konsekuensi asynchronous processing: event yang sudah diterima API belum tentu langsung muncul di `/events`. Selain itu delivery biasanya at-least-once, sehingga duplikasi harus dianggap normal. Karena itu rancangan memakai idempotent consumer dan dedup store persisten.

## T2 - Kapan Memilih Publish-Subscribe dibanding Client-Server

Publish-subscribe dipilih ketika producer dan consumer perlu dipisahkan dalam waktu, lokasi, dan jumlah. Pada model client-server biasa, client mengirim request ke server dan mengharapkan response langsung dari server yang sama. Model itu cocok untuk operasi sinkron sederhana. Namun log aggregator membutuhkan ingestion berkecepatan tinggi, toleransi terhadap lonjakan traffic, dan pemrosesan asynchronous. Publisher sebaiknya tidak menunggu semua proses dedup dan audit selesai sebelum request dianggap diterima.

Dengan pub-sub, aggregator dapat menerima event lalu memasukkannya ke broker. Worker kemudian memproses event secara paralel. Jika worker lambat, broker menjadi buffer. Jika ada duplikasi atau retry, storage tetap menjaga idempotency. Ini sejalan dengan pembahasan arsitektur terdistribusi bahwa pemisahan komponen dapat meningkatkan scalability dan evolvability, tetapi membutuhkan protokol komunikasi dan koordinasi yang jelas (Coulouris et al., 2012). Dalam proyek ini, Redis Streams menjadi mekanisme komunikasi asynchronous internal, sedangkan FastAPI tetap menyediakan interface HTTP sederhana untuk publisher dan user demo.

## T3 - At-Least-Once vs Exactly-Once Delivery dan Peran Idempotent Consumer

At-least-once delivery berarti setiap pesan akan dikirim minimal satu kali, tetapi mungkin dikirim lebih dari sekali. Exactly-once delivery berarti efek pemrosesan terjadi tepat satu kali. Dalam sistem terdistribusi nyata, exactly-once sulit dicapai secara end-to-end karena crash, retry, timeout, dan ketidakpastian status pesan dapat membuat producer atau broker mengirim ulang pesan. Coulouris et al. (2012) menjelaskan bahwa failure dan komunikasi tidak andal adalah persoalan mendasar dalam sistem terdistribusi.

Rancangan ini memilih at-least-once delivery dan membuat efeknya idempotent. Redis Streams menyimpan pesan, worker memprosesnya, lalu melakukan ack setelah transaksi database sukses. Jika worker crash sebelum ack, pesan dapat dikirim ulang. Duplikasi tersebut tidak merusak data karena consumer menggunakan `(topic, event_id)` sebagai kunci dedup. Jika event yang sama diproses ulang, insert ke `processed_events` akan conflict dan diabaikan. Dengan begitu, delivery boleh terjadi lebih dari sekali, tetapi side effect penting hanya terjadi sekali.

## T4 - Skema Penamaan Topic dan Event ID

Topic dipakai sebagai namespace log, misalnya `auth.login`, `payments`, `inventory`, dan `system.metrics`. Format topic dibatasi pada huruf, angka, titik, garis bawah, titik dua, dan tanda hubung agar mudah dipakai sebagai label metrik serta aman untuk query. `event_id` adalah identifier unik di dalam satu topic. Constraint database menggunakan pasangan `(topic, event_id)`, bukan hanya `event_id`, sehingga dua domain berbeda boleh memakai id yang sama tanpa konflik.

Skema ini membantu dedup karena collision domain menjadi jelas. Publisher dapat memakai UUID, ULID, atau id deterministik dari sumber event. Dalam implementasi demo, publisher default memakai UUID v4. Untuk demo persistence, env `SEED` menghasilkan id deterministik agar event yang sama dapat dikirim ulang setelah container recreate. Bab naming dalam sistem terdistribusi menekankan bahwa nama harus dapat mengidentifikasi resource secara stabil dalam sistem yang komponennya terpisah (Coulouris et al., 2012). Di sini, nama stabilnya adalah kombinasi topic dan event id.

## T5 - Ordering Praktis

Sistem tidak memaksakan total ordering global untuk semua event. Total ordering lintas publisher dan lintas topic membutuhkan koordinasi tambahan yang mahal, misalnya sequencer global atau konsensus. Untuk log aggregator, kebutuhan utamanya adalah menampilkan event secara masuk akal dan mencegah duplikasi. Karena itu ordering praktis memakai dua data: timestamp dari event dan `logical_seq` dari id database saat event unik berhasil disimpan.

Timestamp membantu membaca urutan kejadian dari perspektif producer, tetapi clock antar mesin bisa berbeda. `logical_seq` membantu memberi urutan monotonic lokal di storage untuk event yang sudah diproses. Kombinasi ini memberi ordering yang stabil untuk tampilan `/events`, tetapi tidak diklaim sebagai causal ordering sempurna. Pembahasan waktu dan ordering pada sistem terdistribusi menunjukkan bahwa clock fisik memiliki keterbatasan, sehingga desain sering memakai logical ordering atau menerima ordering parsial sesuai kebutuhan aplikasi (Coulouris et al., 2012).

## T6 - Failure Modes dan Mitigasi

Failure mode utama adalah duplikasi event, crash worker, restart container, broker pending message, dan storage yang harus tetap konsisten. Publisher juga bisa melakukan retry ketika request gagal, sehingga event yang sama mungkin masuk lebih dari sekali. Worker aggregator bisa crash setelah membaca pesan tetapi sebelum ack. Dalam kondisi itu, Redis Streams menyimpan pesan sebagai pending. Implementasi memakai `XAUTOCLAIM` untuk mengambil ulang pesan stale agar dapat diproses worker lain.

Mitigasi paling penting adalah dedup store persisten. PostgreSQL menyimpan `processed_events` pada named volume `pg_data`, sehingga container recreate tidak menghapus riwayat dedup. Ack Redis dilakukan setelah transaksi database selesai. Jika worker crash sebelum ack, event akan diproses ulang, tetapi insert kedua akan conflict dan dihitung sebagai duplicate. Desain ini mengikuti prinsip fault tolerance bahwa sistem harus tetap benar meskipun sebagian komponen gagal, bukan mengasumsikan jaringan dan proses selalu sehat (Coulouris et al., 2012).

## T7 - Eventual Consistency pada Aggregator

Aggregator bersifat eventually consistent karena publish dan processing dipisahkan oleh queue. Setelah `POST /publish` berhasil, event sudah diterima dan dimasukkan ke Redis Streams, tetapi belum tentu langsung muncul di `/events`. Event baru terlihat setelah worker membaca stream dan transaksi database selesai. Keterlambatan ini adalah trade-off dari desain asynchronous. Keuntungannya, sistem lebih responsif saat menerima batch besar dan worker dapat memproses secara paralel.

Eventual consistency tetap aman karena operasi write dirancang idempotent. Jika event diproses ulang, database tidak menghasilkan record unik kedua. Jika ada beberapa worker, hanya satu yang berhasil insert untuk `(topic, event_id)` yang sama. Dengan kata lain, state akhir storage akan konvergen ke kumpulan event unik walaupun jalur menuju state itu berisi retry dan duplikasi. Coulouris et al. (2012) membahas bahwa konsistensi dalam sistem terdistribusi sering melibatkan trade-off antara ketersediaan, performa, dan kekuatan jaminan konsistensi. Rancangan ini memilih konsistensi akhir yang diperkuat oleh dedup transaksional.

## T8 - Desain Transaksi: ACID, Isolation, dan Lost Update

Transaksi utama berada pada fungsi pemrosesan event. Dalam satu transaksi, sistem menaikkan counter `received`, mencoba insert event unik, menaikkan counter `unique_processed` atau `duplicate_dropped`, dan menulis audit log. Atomicity memastikan perubahan ini tidak setengah jalan. Jika transaksi gagal, pesan Redis tidak di-ack sehingga bisa diproses ulang. Consistency dijaga oleh constraint unik `(topic, event_id)`. Durability diberikan oleh PostgreSQL dan named volume.

Isolation level yang dipakai adalah `READ COMMITTED` pada PostgreSQL. Level ini cukup karena konflik dedup tidak diselesaikan melalui read-then-write manual, melainkan melalui unique index dan `ON CONFLICT DO NOTHING`. Lost update pada counter dicegah dengan SQL increment atomik `value = value + 1`, bukan membaca nilai counter ke aplikasi lalu menulis ulang. Bab transaksi menekankan pentingnya ACID untuk menjaga correctness saat operasi concurrent terjadi (Coulouris et al., 2012). Dalam proyek ini, correctness terletak pada fakta bahwa event unik tidak dapat diproses dua kali walau banyak worker aktif.

## T9 - Kontrol Konkurensi: Locking, Unique Constraint, dan Idempotent Write Pattern

Kontrol konkurensi paling penting adalah unique constraint pada tabel `processed_events`. Ketika dua worker memproses event sama secara paralel, keduanya mencoba insert `(topic, event_id)` yang sama. Database mengizinkan hanya satu transaksi berhasil. Transaksi lain tidak merusak data; ia menerima conflict dan operasi insert diabaikan. Inilah idempotent write pattern: request yang sama dapat diulang tanpa menghasilkan side effect ganda.

Pendekatan ini lebih kuat daripada melakukan `SELECT` dahulu untuk mengecek apakah event sudah ada. Pada pola read-then-insert, dua worker bisa sama-sama membaca data belum ada lalu bersaing saat insert. Dengan unique constraint, mekanisme locking dan conflict detection didelegasikan ke database. Counter juga diperbarui secara atomik. Bab kontrol konkurensi menjelaskan masalah seperti lost update dan race condition saat transaksi berjalan bersamaan (Coulouris et al., 2012). Implementasi ini membuktikannya lewat test `test_concurrent_duplicate_processing_inserts_once`, yaitu 50 operasi concurrent hanya menghasilkan satu event unik.

## T10 - Orkestrasi Compose, Keamanan Lokal, Persistensi, dan Observability

Docker Compose mengorkestrasi empat service: aggregator, publisher, broker, dan storage. Redis dan PostgreSQL berada di network `backend` yang bersifat internal dan tidak membuka port host. Aggregator expose port `8080` untuk demo lokal. Ini memenuhi batasan bahwa sistem berjalan pada jaringan lokal Compose tanpa layanan eksternal publik. Healthcheck disediakan untuk Redis, PostgreSQL, dan aggregator `/readyz`.

Persistensi dilakukan dengan named volume `pg_data` untuk PostgreSQL dan `broker_data` untuk Redis AOF. Dengan demikian data tetap ada setelah container dihapus atau aggregator dibuat ulang. Observability diberikan melalui endpoint `/stats`, `/audit`, `/healthz`, `/readyz`, dan logging worker yang membedakan event `processed` dan `duplicate dropped`. Bab sistem berbasis web, storage, dan koordinasi menekankan pentingnya pengelolaan resource, fault tolerance, dan monitoring dalam sistem terdistribusi (Coulouris et al., 2012). Compose membuat deployment lokal dapat direproduksi untuk demo dan pengujian.

## Kesimpulan

Sistem ini menunjukkan pola praktis untuk membangun aggregator terdistribusi yang menerima at-least-once delivery tetapi tetap menjaga konsistensi data. Kunci correctness adalah idempotent consumer, persistent dedup store, transaksi database, dan kontrol konkurensi berbasis unique constraint. Redis Streams memberi decoupling dan retry, sedangkan PostgreSQL menjadi sumber kebenaran untuk event unik, stats, dan audit.

## Referensi

Coulouris, G., Dollimore, J., Kindberg, T., & Blair, G. (2012). *Distributed systems: Concepts and design* (5th ed.). Addison-Wesley.
