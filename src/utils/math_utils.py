import hashlib
from pathlib import Path


def calculate_sha256(file_path: Path) -> str:
    """
    Calculate the SHA-256 hash of a file.

    The file is read in chunks to avoid loading the entire file
    into memory, making it suitable for large video files.

    Args:
        file_path: Path to the file to hash.

    Returns:
        str: Hexadecimal SHA-256 digest.
    """
    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            sha256.update(chunk)

    return sha256.hexdigest()
