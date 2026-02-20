# Parexa Interface

Project ini dibuat sebagai Final Project Sanber Code Bootcamp batch 8.

**Parexa** adalah AI Chat Interface berbasis **Flask** yang mendukung:
- **RAG (Retrieval-Augmented Generation)** lewat unggah dokumen
- **Fallback OCR** untuk PDF hasil scan / halaman dengan teks minim
- **Genesis mode (multi-agent)**: draft → critics → synthesis/final
- **Riwayat chat persisten** (conversation storage)

![Dark Parexa UI](https://images2.imgbox.com/95/cc/YVmQe70h_o.jpeg)
![Light Parexa UI](https://images2.imgbox.com/ba/63/ouoX5xdX_o.jpeg)

---

## Highlights

- Upload & RAG untuk: `.pdf`, `.md`, `.txt`
- OCR fallback untuk PDF scan / sparse text menggunakan **EasyOCR**
- Genesis mode: draft → critics → final refinement (opsional)
- Jalur eksekusi async (executor pools) untuk workload upload/chat yang berat
- Persistence via **ChromaDB** (conversation history + vector store)
- Runtime data dipusatkan di folder `runtime/` (default) atau diarahkan via `PAREXA_DATA_DIR`

---

## Tech Stack

- Backend: Flask
- Frontend: HTML, CSS, Vanilla JavaScript
- AI/ML: LlamaIndex, Cerebras API (chat), Google GenAI Embeddings (embedding), PyMuPDF, EasyOCR
- Storage/Vector DB: ChromaDB

---

## Requirements

- Python `3.10+`
- Required API keys:
  - `CEREBRAS_API_KEY`
  - `GOOGLE_API_KEY`

---

## Quick Start

1. Clone repo
```bash
git clone <repository-url>
cd Parexa
```
2. Buat virtual environment
```bash
python -m venv venv
# Windows
.\venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```
3. Install dependencies
```bash
pip install -r requirements.txt
```
4. Copy `.env.example` ke `.env` dan isi API keys
```bash
# Windows
copy .env.example .env
# Linux/Mac
cp .env.example .env
```
5. Jalankan aplikasi
```bash
python app.py
```
Aplikasi akan berjalan di `http://localhost:5000`


## Environment Configuration
Minimal required:
```
CEREBRAS_API_KEY=your_cerebras_key_here
GOOGLE_API_KEY=your_google_ai_key_here
```
Common optional:
```
# Optional: simpan runtime data di luar root repo
PAREXA_DATA_DIR=runtime

# Flask
FLASK_ENV=development
PORT=5000

# Embedding model (Google)
EMBEDDING_MODEL=models/gemini-embedding-001

# Ingestion + execution tuning
INGEST_OCR_SPARSE_THRESHOLD=120
PAREXA_IO_WORKERS=4
PAREXA_CPU_WORKERS=4
GENESIS_PARALLEL_CRITICS=3
```

---
## Usage Notes

- Upload dokumen via UI (ikon attachment). Setelah upload sukses, file akan diproses dan diindex.

- Untuk request yang membawa files / file_ids, Parexa akan memprioritaskan RAG mode (jawab berdasarkan dokumen).

- Jika browsing mode ada, tapi request juga menyertakan file, browsing akan dioverride agar jawaban fokus pada konteks dokumen.

---
## Troubleshooting
### 1) Jawaban tidak menyertakan konteks file (RAG tidak kepakai)

Checklist:

>Pastikan upload mengembalikan file_id.

>Pastikan request chat menyertakan files atau file_ids.

>Ajukan pertanyaan spesifik. Upload tanpa pertanyaan biasanya tidak memicu retrieval yang berarti.

>Cek bagian warnings pada respons upload (kalau ada) untuk indikasi masalah parsing.

### 2) Upload PDF scan tapi teks kosong

Itu normal untuk PDF yang isinya gambar (scan).

>Pastikan OCR fallback aktif dan threshold sesuai kebutuhan.

>Coba turunkan INGEST_OCR_SPARSE_THRESHOLD jika terlalu banyak halaman dianggap “sparse”.

---
## W.I.P
- Image Understanding Document
- Episodic and Semantic Memory system
- Multiple Swarm Agents