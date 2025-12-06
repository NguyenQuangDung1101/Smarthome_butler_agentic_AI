import ollama
import requests
import logging
import base64
from pathlib import Path
import faiss
import numpy as np
import json
import time as _time
from sentence_transformers import SentenceTransformer

# Set up logging
logger = logging.getLogger("OLLama")
logging.basicConfig(level=logging.INFO)

class Copilot:
    def __init__(self, host="http://localhost:11434", model="gemma3:4b", server_host="http://localhost:5001"):
        self.host = host
        self.model = model
        self.server_host = server_host
        self.client = ollama.Client(host=self.host)
 
    def list_models(self):
        try:
            res = requests.get(self.host + "/api/tags", verify=False)
            data = res.json()
            return [m["model"] for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"Error fetching model list: {e}")
            return []

    def infer(self, user_prompt, system_prompt=None, image_path=None,
              timeout=10000, retries=5, backoff=3):

        prompt = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
        # print("Prompt to send:\n", prompt)
        # Base kwargs for Ollama client
        kwargs = {
            "model": self.model,
            "prompt": prompt,
            "options": {
                    "gpu_layers": 999
            }
        }

        # Only add image if model supports it (your original rule)
        if "gemma3:4b" in self.model and image_path:
            try:
                with open(image_path, "rb") as f:
                    image_bytes = f.read()
                image_b64 = base64.b64encode(image_bytes).decode("utf-8")
                kwargs["images"] = [image_b64]
            except Exception as e:
                logger.error(f"Error loading image: {e}")

        last_err = None

        for attempt in range(retries):
            try:
                # For cloud/large models, use HTTP streaming which is more resilient
                use_streaming_http = "cloud" in (self.model or "").lower()

                if use_streaming_http:
                    payload = {
                        "model": self.model,
                        "prompt": prompt,
                        "options": kwargs.get("options", {}),
                        "stream": True,
                    }
                    if "images" in kwargs:
                        payload["images"] = kwargs["images"]

                    url = f"{self.host}/api/generate"
                    resp_text = ""
                    with requests.post(url, json=payload, stream=True, timeout=timeout, verify=False) as r:
                        r.raise_for_status()
                        # First try to read line by line (JSON-lines)
                        for raw in r.iter_lines(decode_unicode=False):
                            if raw is None:
                                continue
                            try:
                                line = raw.decode("utf-8")
                            except Exception:
                                continue
                            line = line.strip()
                            if not line:
                                continue

                            # Support SSE-style 'data: {...}' lines
                            if line.startswith("data:"):
                                line = line[len("data:"):].strip()

                            # Some servers prefix with event: or other SSE fields; ignore those
                            if line.startswith("event:") or line.startswith("id:"):
                                continue

                            # Try JSON parse first
                            try:
                                obj = json.loads(line)
                            except Exception:
                                # Not JSON; skip this line entirely (don't append raw JSON)
                                logger.debug(f"Skipping non-JSON line: {line[:100]}...")
                                continue

                            # Accept several possible response fields
                            chunk = None
                            for k in ("response", "text", "chunk", "data"):
                                if isinstance(obj, dict) and k in obj:
                                    val = obj.get(k)
                                    if isinstance(val, str) and val.strip():  # Only add non-empty strings
                                        chunk = val
                                        break

                            # If object directly is a string
                            if chunk is None and isinstance(obj, str) and obj.strip():
                                chunk = obj

                            if chunk:
                                resp_text += chunk

                            # If the server includes a done flag, stop
                            if isinstance(obj, dict) and obj.get("done"):
                                break

                    if resp_text.strip():
                        # Filter out responses that are clearly just JSON metadata
                        if not (resp_text.startswith('{"model"') and '"done":' in resp_text):
                            return resp_text
                        else:
                            logger.warning("Received only JSON metadata, no actual response content")
                            resp_text = ""  # Clear it and try fallback
                    
                    if not resp_text.strip():
                        logger.warning("Empty response from streaming, trying non-streaming fallback")
                        try:
                            # Try a non-streaming request as fallback
                            fallback_payload = payload.copy()
                            fallback_payload["stream"] = False
                            r2 = requests.post(url, json=fallback_payload, timeout=timeout, verify=False)
                            r2.raise_for_status()
                            try:
                                data = r2.json()
                            except Exception:
                                data = {"response": r2.text}

                            # collect text from common fields
                            if isinstance(data, dict):
                                for k in ("response", "text", "result", "data"):
                                    if k in data and isinstance(data[k], str) and data[k].strip():
                                        resp_text = data[k]
                                        break
                            elif isinstance(data, str):
                                resp_text = data
                        except Exception as e:
                            logger.debug(f"Non-streaming fallback failed: {e}")
                    
                    if resp_text.strip():
                        return resp_text
                    raise RuntimeError("Empty response (streaming HTTP)")
                else:
                    # Original client path
                    response = self.client.generate(**kwargs)
                    return response["response"]

            except Exception as e:
                last_err = e
                logger.error(f"Inference failed (attempt {attempt+1}/{retries}): {e}")
                if attempt < retries:
                    _time.sleep(backoff ** attempt)

        logger.error(f"Inference failed: {last_err}")
        return None

    def infer_client(self, user_prompt, system_prompt="You are a helpful assistant.", image_path=None, timeout=30, retries=2, backoff=1.5):
        image_b64 = None
        if image_path:
            try:
                with open(image_path, "rb") as f:
                    image_b64 = base64.b64encode(f.read()).decode("utf-8")
            except Exception as e:
                logger.error(f"{e}")
        payload = {
            "model": self.model,
            "prompt": user_prompt or "",
            "system_prompt": system_prompt or "",
            "image_b64": image_b64
        }
        url = f"{self.server_host}/infer"
        last_err = None
        for attempt in range(retries + 1):
            try:
                res = requests.post(url, json=payload, timeout=timeout)
                if res.ok:
                    data = res.json()
                    if data.get("status") == "ok":
                        return data.get("llm_out", "")
                    logger.error(f"{data}")
                    return None
                else:
                    last_err = RuntimeError(f"HTTP {res.status_code} {res.text}")
            except Exception as e:
                last_err = e
            if attempt < retries:
                import time
                time.sleep(backoff ** attempt)
        logger.error(f"{last_err}")
        return None

class KnowledgeBase:
    def __init__(self,
                 model_name: str = "all-MiniLM-L6-v2",
                 chunk_size: int = 800,
                 chunk_overlap: int = 100,
                 chunk_by: str = "words"):
        self.model_name = model_name
        self.embedder = SentenceTransformer(model_name)
        self.chunk_size = int(chunk_size)
        self.chunk_overlap = int(chunk_overlap)
        self.chunk_by = chunk_by
        self.raw_documents = []
        self.texts = []
        self.sources = []
        self.index = None

    def _chunk_document(self, text: str):
        if not text:
            return []
        if self.chunk_by == "chars":
            n = len(text)
            step = max(1, self.chunk_size - self.chunk_overlap)
            return [c for c in (text[i:i + self.chunk_size] for i in range(0, n, step)) if c.strip()]
        else:
            tokens = text.split()
            n = len(tokens)
            step = max(1, self.chunk_size - self.chunk_overlap)
            chunks = []
            for i in range(0, n, step):
                chunk_tokens = tokens[i:i + self.chunk_size]
                if chunk_tokens:
                    chunks.append(" ".join(chunk_tokens))
            return [c for c in chunks if c.strip()]

    def build(self, documents):
        """Build FAISS index from list of text documents (with chunking)."""
        self.raw_documents = list(documents)

        # chunk
        all_chunks = []
        sources = []
        for doc_id, doc in enumerate(self.raw_documents):
            chunks = self._chunk_document(doc)
            for c_idx, c in enumerate(chunks):
                all_chunks.append(c)
                sources.append((doc_id, c_idx))

        # stats
        total_docs = len(self.raw_documents)
        total_chunks = len(all_chunks)
        lengths = [len(c.split()) if self.chunk_by == "words" else len(c) for c in all_chunks]
        avg_len = (sum(lengths) / total_chunks) if total_chunks else 0
        min_len = min(lengths) if lengths else 0
        max_len = max(lengths) if lengths else 0

        logger.info(
            "KB build: chunking_config = {"
            f"'chunk_size': {self.chunk_size}, "
            f"'chunk_overlap': {self.chunk_overlap}, "
            f"'chunk_by': '{self.chunk_by}'"
            "}"
        )
        logger.info(
            "KB build: stats = {"
            f"'num_input_docs': {total_docs}, "
            f"'num_chunks': {total_chunks}, "
            f"'avg_chunk_len_{'words' if self.chunk_by=='words' else 'chars'}': {avg_len:.2f}, "
            f"'min_len': {min_len}, "
            f"'max_len': {max_len}"
            "}"
        )

        if total_chunks == 0:
            logger.warning("Knowledge base is empty after chunking. Nothing to index.")
            self.texts, self.sources, self.index = [], [], None
            return

        self.texts = all_chunks
        self.sources = sources

        # embeddings + FAISS (inner product over normalized vectors)
        embeddings = self.embedder.encode(
            self.texts,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)
        logger.info(f"Knowledge base built with {total_chunks} chunks.")

    def retrieve(self, query, k=3):
        """Retrieve top-k most relevant chunks."""
        if not self.index:
            logger.warning("Knowledge base is empty. Run build() or load() first.")
            return []
        q_emb = self.embedder.encode([query], convert_to_numpy=True, normalize_embeddings=True)
        D, I = self.index.search(q_emb, k)
        return [self.texts[i] for i in I[0] if 0 <= i < len(self.texts)]

    def save(self, folder_path: str):
        p = Path(folder_path)
        p.mkdir(parents=True, exist_ok=True)

        if self.index is None or not self.texts:
            raise RuntimeError("Nothing to save: build() first.")

        # save faiss index
        faiss.write_index(self.index, str(p / "index.faiss"))

        # save chunks
        with open(p / "texts.jsonl", "w", encoding="utf-8") as f:
            for t in self.texts:
                f.write(json.dumps({"text": t}, ensure_ascii=False) + "\n")

        # save sources
        with open(p / "sources.jsonl", "w", encoding="utf-8") as f:
            for doc_id, chunk_idx in self.sources:
                f.write(json.dumps({"doc_id": doc_id, "chunk_idx": chunk_idx}) + "\n")

        # save metadata/config
        meta = {
            "model_name": self.model_name,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "chunk_by": self.chunk_by
        }
        with open(p / "meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        logger.info(f"KB saved to: {p.resolve()}")

    def load(self, folder_path: str):
        """Load FAISS index + chunks + metadata from folder."""
        p = Path(folder_path)
        idx_path = p / "index.faiss"
        texts_path = p / "texts.jsonl"
        sources_path = p / "sources.jsonl"
        meta_path = p / "meta.json"

        if not (idx_path.exists() and texts_path.exists() and sources_path.exists() and meta_path.exists()):
            raise FileNotFoundError("KB folder is missing required files (index.faiss, texts.jsonl, sources.jsonl, meta.json).")

        # load meta and (re)create embedder with same model
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        stored_model = meta.get("model_name", self.model_name)
        if stored_model != self.model_name:
            logger.warning(f"KB stored model '{stored_model}' differs from current '{self.model_name}'. Reinitializing embedder to '{stored_model}'.")
            self.model_name = stored_model
            self.embedder = SentenceTransformer(self.model_name)

        self.chunk_size = meta.get("chunk_size", self.chunk_size)
        self.chunk_overlap = meta.get("chunk_overlap", self.chunk_overlap)
        self.chunk_by = meta.get("chunk_by", self.chunk_by)

        # load faiss
        self.index = faiss.read_index(str(idx_path))

        # load texts
        texts = []
        with open(texts_path, "r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                texts.append(obj["text"])
        self.texts = texts

        # load sources
        sources = []
        with open(sources_path, "r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                sources.append((obj["doc_id"], obj["chunk_idx"]))
        self.sources = sources

        logger.info(f"KB loaded from: {p.resolve()} (chunks={len(self.texts)})")



def load_documents_from_folder(folder_path):
    folder = Path(folder_path)
    docs = []
    for f in folder.glob("*.txt"):
        try:
            content = f.read_text(encoding="utf-8").strip()
            if content:
                docs.append(content)
        except Exception as e:
            logger.error(f"Error reading {f}: {e}")
    logger.info(f"Loaded {len(docs)} documents from {folder_path}")
    return docs

def load_system_prompt(filename):
    try:
        with open(filename, 'r') as file:
            return file.read().strip()
    except Exception as e:
        logger.error(f"Error reading system prompt from file: {e}")
        return None



if __name__ == "__main__":
    # *gpt-oss:20b-cloud
    # qwen3:1.7b
    # qwen3:4b
    # qwen3:8b
    copilot = Copilot(
        host="http://localhost:11434",
        model="qwen3:1.7b"
    )
    print(copilot.list_models())

    # role_sys_prompt = load_system_prompt('./system_prompt_doc/role.txt')
    # instruction_sys_prompt = load_system_prompt('./system_prompt_doc/instruction.txt')
    # parts = [role_sys_prompt, instruction_sys_prompt]
    # sys_prompt = "\n\n".join([p for p in parts if p])
    # sys_prompt = ""

    # # input
    # question = "how many light in the bedroom?"
    # # image_path = r""

    # # ###########################################################################
    # # # Use kb from raw text
    # docs = load_documents_from_folder("./knowledge_base")
    # kb = KnowledgeBase(
    #     model_name="all-MiniLM-L6-v2",
    #     chunk_size=800,
    #     chunk_overlap=100,
    #     chunk_by="words"
    # )
    # kb.build(docs)
    # context_docs = kb.retrieve(question, k=3)
    # context = "\n\n".join(context_docs)
    # print(context)
    # question = f"Use the following knowledge to answer:\n{context}\n\nQuestion: {question}"


    # ###########################################################################
    # # # Save and use kb from vector database
    # # docs = load_documents_from_folder("./knowledge_base")
    # # kb = KnowledgeBase(model_name="all-MiniLM-L6-v2", chunk_size=800, chunk_overlap=100, chunk_by="words")
    # # kb.build(docs)
    # # kb.save("./kb_store/test1")
    # # kb = KnowledgeBase()
    # # kb.load("./kb_store/test1")
    # # context_docs = kb.retrieve(question, k=3)
    # # context = "\n\n".join(context_docs)
    # # print(context)
    # # question = f"Use the following knowledge to answer:\n{context}\n\nQuestion: {question}"




    # # Run inference
    # result = copilot.infer(question, sys_prompt)
    # print("Answer:\n", result)

