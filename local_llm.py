import ollama
import requests
import logging
import base64
from pathlib import Path
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# Set up logging
logger = logging.getLogger("OLLama")
logging.basicConfig(level=logging.INFO)

class Copilot:
    def __init__(self, host="http://localhost:11434", model="gemma3:4b"):
        self.host = host
        self.model = model
        self.client = ollama.Client(host=self.host)
 
    def list_models(self):
        try:
            res = requests.get(self.host + "/api/tags", verify=False)
            data = res.json()
            return [m["model"] for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"Error fetching model list: {e}")
            return []

    def infer(self, user_prompt, system_prompt="You are a helpful assistant.", image_path=None):
        prompt = f"{system_prompt}\n\n{user_prompt}"

        kwargs = {
            "model": self.model,
            "prompt": prompt,
            "options": {
                "gpu_layers": 999
            }
        }

        # Only add image if model supports it
        if "gemma3:4b" in self.model and image_path:
            try:
                with open(image_path, "rb") as f:
                    image_bytes = f.read()
                image_b64 = base64.b64encode(image_bytes).decode("utf-8")
                kwargs["images"] = [image_b64]
            except Exception as e:
                logger.error(f"Error loading image: {e}")

        try:
            response = self.client.generate(**kwargs)
            return response["response"]
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            return None


class KnowledgeBase:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self.embedder = SentenceTransformer(model_name)
        self.texts = []
        self.index = None

    def build(self, documents):
        """Build FAISS index from list of text documents."""
        self.texts = documents
        embeddings = self.embedder.encode(documents, convert_to_numpy=True, normalize_embeddings=True)
        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)
        logger.info(f"Knowledge base built with {len(documents)} documents.")

    def retrieve(self, query, k=3):
        """Retrieve top-k most relevant documents."""
        if not self.index:
            logger.warning("Knowledge base is empty. Run build() first.")
            return []
        q_emb = self.embedder.encode([query], convert_to_numpy=True, normalize_embeddings=True)
        D, I = self.index.search(q_emb, k)
        return [self.texts[i] for i in I[0]]



def load_documents_from_folder(folder_path):
    """Load all text files in a folder as separate documents."""
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
    # qwen3:1.7b
    # qwen3:4b
    # qwen3:8b
    copilot = Copilot(
        host="http://localhost:11434",
        model="qwen3:1.7b"
    )

    role_sys_prompt = load_system_prompt('./system_prompt_doc/role.txt')
    instruction_sys_prompt = load_system_prompt('./system_prompt_doc/instruction.txt')
    parts = [role_sys_prompt, instruction_sys_prompt]
    sys_prompt = "\n\n".join([p for p in parts if p])
    sys_prompt = ""


    # input
    question = "how many light in the bedroom?"
    # image_path = r""

    docs = load_documents_from_folder("./knowledge_base")
    if docs:
        kb = KnowledgeBase()
        kb.build(docs)
        context_docs = kb.retrieve(question, k=3)
        context = "\n\n".join(context_docs)
        print(context)
        question = f"Use the following knowledge to answer:\n{context}\n\nQuestion: {question}"



    # Run inference
    result = copilot.infer(question, sys_prompt)
    print("Answer:\n", result)