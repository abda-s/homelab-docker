from pathlib import Path
import time
from src.utils import soft_delete

def test_soft_delete():
    # Create a dummy file
    test_file = Path("test_soft_delete.txt")
    test_file.touch()
    print(f"Created {test_file}")

    # Soft delete it
    soft_delete(test_file)
    print(f"Soft deleted {test_file}")

    # Check if original is gone
    if test_file.exists():
        print("FAIL: Original file still exists")
    else:
        print("PASS: Original file is gone")

    # Check if renamed file exists
    found = False
    for p in Path(".").glob("deleted_*_test_soft_delete.txt"):
        print(f"PASS: Found soft deleted file: {p}")
        found = True
        # Cleanup
        p.unlink()
    
    if not found:
        print("FAIL: Soft deleted file not found")

if __name__ == "__main__":
    test_soft_delete()
