from huggingface_hub import HfApi
from dotenv import load_dotenv
import os

load_dotenv()
hf_api = HfApi(token=os.getenv('HF_TOKEN'))
full_repo_id = f"{os.getenv('HF_USERNAME')}/{os.getenv('HF_REPO')}"

print(f"Checking repo: {full_repo_id}")
try:
    info = hf_api.repo_info(full_repo_id)
    print(f"Repo exists: {info.id}, Type: {info.type}")
except Exception as e:
    print(f"Repo does not exist or error: {e}")