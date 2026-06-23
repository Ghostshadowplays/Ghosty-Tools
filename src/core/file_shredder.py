import os
import secrets
import logging

logger = logging.getLogger(__name__)

class FileShredder:
    @staticmethod
    def shred(file_path, passes=3):
        """Securely delete a file by overwriting it multiple times."""
        if not os.path.isfile(file_path):
            return False, "File not found."
        
        try:
            length = os.path.getsize(file_path)
            with open(file_path, "ba+", buffering=0) as f:
                for _ in range(passes):
                    f.seek(0)
                    f.write(secrets.token_bytes(length))
            
            os.remove(file_path)
            return True, f"File {file_path} shredded successfully."
        except Exception as e:
            logger.error(f"Error shredding file {file_path}: {e}")
            return False, str(e)
