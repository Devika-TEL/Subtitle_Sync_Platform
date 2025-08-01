import os
import uuid
from fastapi import UploadFile

from config import settings

def get_storage_dir(kind):
    base = settings.FILE_STORAGE_PATH or "processed"
    path = os.path.join(base, kind)
    os.makedirs(path, exist_ok=True)
    return path

# PUBLIC_INTERFACE
def save_upload_file(upload_file: UploadFile, kind: str):
    """Save uploaded file and return file_id, file_path"""
    storage_dir = get_storage_dir(kind)
    file_id = str(uuid.uuid4())
    filename = f"{file_id}_{upload_file.filename}"
    file_path = os.path.join(storage_dir, filename)
    with open(file_path, "wb") as f:
        f.write(upload_file.file.read())
    return file_id, file_path

# PUBLIC_INTERFACE
def get_file_path(path):
    """Returns the file system path for the given logical file path."""
    return path

# PUBLIC_INTERFACE
def delete_file_if_exists(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

# PUBLIC_INTERFACE
def save_file_bytes(bytes_content, out_path):
    with open(out_path, "wb") as f:
        f.write(bytes_content)
    return out_path
