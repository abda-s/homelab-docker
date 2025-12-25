import logging
import sys
from pathlib import Path
from src.ffmpeg import remove_silence, get_mean_volume

# Setup basic logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("test_vad")

def test_vad():
    # We need a real audio file to test this properly, but we can at least check if the function runs
    # and handles a missing file gracefully or if we can mock it.
    # Since we can't easily create a valid audio file with silence without ffmpeg installed and working,
    # we will rely on the fact that the user has ffmpeg.
    
    # Let's try to run it on a non-existent file and see if it handles the error as expected (returning False)
    # This confirms the function is callable and imports are correct.
    
    fake_file = Path("non_existent_audio.wav")
    clean_file = Path("clean_non_existent.flac")
    
    logger.info("Testing VAD on non-existent file...")
    result = remove_silence(fake_file, clean_file, logger)
    
    if not result:
        logger.info("PASS: remove_silence returned False for missing file")
    else:
        logger.error("FAIL: remove_silence returned True for missing file")

    # Test get_mean_volume
    vol = get_mean_volume(fake_file, logger)
    if vol == -91.0:
        logger.info("PASS: get_mean_volume returned -91.0 for missing file")
    else:
        logger.error(f"FAIL: get_mean_volume returned {vol} for missing file")

if __name__ == "__main__":
    test_vad()
