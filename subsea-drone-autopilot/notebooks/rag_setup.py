# Databricks notebook source
# MAGIC %md
# MAGIC # Subsea Manuals RAG Setup
# MAGIC Reads PDF manuals from UC Volume, chunks them, builds a Vector Search index.

# COMMAND ----------

# MAGIC %pip install pypdf langchain-text-splitters databricks-vectorsearch
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

VOLUME_PATH = "/Volumes/subsea/manuals/pdfs"
VS_ENDPOINT = "subsea-manuals-vs"
VS_INDEX = "subsea.manuals.chunk_index"
EMBEDDING_MODEL = "databricks-bge-large-en"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Read and chunk PDFs

# COMMAND ----------

from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os

splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " "],
)

chunks = []
for fname in dbutils.fs.ls(VOLUME_PATH):
    if not fname.name.endswith(".pdf"):
        continue
    local_path = f"/dbfs{VOLUME_PATH}/{fname.name}"
    reader = PdfReader(local_path)
    doc_name = fname.name.replace(".pdf", "")

    full_text = ""
    for page_num, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        full_text += f"\n[Page {page_num + 1}]\n{text}"

    for i, chunk_text in enumerate(splitter.split_text(full_text)):
        chunks.append({
            "chunk_id": f"{doc_name}__chunk_{i:04d}",
            "doc_name": doc_name,
            "section": f"chunk_{i}",
            "chunk_text": chunk_text,
        })

print(f"Total chunks: {len(chunks)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Write chunks to Delta table

# COMMAND ----------

import pyspark.sql.functions as F

df = spark.createDataFrame(chunks)
df.write.mode("overwrite").saveAsTable("subsea.manuals.chunks")
display(df.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Create Vector Search endpoint and index

# COMMAND ----------

from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient()

# Create endpoint (idempotent)
try:
    vsc.create_endpoint(name=VS_ENDPOINT, endpoint_type="STANDARD")
    print(f"Created VS endpoint: {VS_ENDPOINT}")
except Exception as e:
    if "already exists" in str(e):
        print(f"VS endpoint {VS_ENDPOINT} already exists")
    else:
        raise

# COMMAND ----------

# Create delta-sync index with managed embeddings
try:
    vsc.create_delta_sync_index(
        endpoint_name=VS_ENDPOINT,
        index_name=VS_INDEX,
        source_table_name="subsea.manuals.chunks",
        pipeline_type="TRIGGERED",
        primary_key="chunk_id",
        embedding_source_column="chunk_text",
        embedding_model_endpoint_name=EMBEDDING_MODEL,
    )
    print(f"Created VS index: {VS_INDEX}")
except Exception as e:
    if "already exists" in str(e):
        print(f"VS index {VS_INDEX} already exists — syncing…")
        idx = vsc.get_index(VS_ENDPOINT, VS_INDEX)
        idx.sync()
    else:
        raise

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Test query

# COMMAND ----------

idx = vsc.get_index(VS_ENDPOINT, VS_INDEX)

results = idx.similarity_search(
    columns=["doc_name", "section", "chunk_text"],
    query_text="What are the criteria for recoating riser clamps?",
    num_results=3,
)

for row in results.get("result", {}).get("data_array", []):
    print(f"\n📄 {row[0]} | {row[1]}")
    print(f"   {row[2][:200]}…")
