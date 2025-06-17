import torch
from faster_whisper import WhisperModel
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def download_whisper_models():
    """
    Downloads and caches the faster-whisper models.
    """
    models = ["base", "small"]
    for model_name in models:
        try:
            logger.info(f"Downloading Whisper model: '{model_name}'...")
            # This will download and cache the model if not present
            WhisperModel(model_name, device="cpu", compute_type="int8")
            logger.info(f"✅ Whisper model '{model_name}' is cached.")
        except Exception as e:
            logger.error(f"❌ Failed to download Whisper model '{model_name}': {e}")
            logger.error("Please check your internet connection and try again.")

def download_silero_vad():
    """
    Downloads both the standard and ONNX versions of the Silero VAD model.
    """
    torch_hub_dir = torch.hub.get_dir()
    logger.info(f"Torch hub cache is located at: {torch_hub_dir}")

    # --- Download Standard PyTorch Model ---
    try:
        logger.info("Checking for standard Silero VAD model...")
        torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            onnx=False  # Explicitly request the standard PyTorch model
        )
        logger.info("✅ Standard Silero VAD model is cached.")
    except Exception as e:
        logger.error(f"❌ Failed to download standard Silero VAD model: {e}")

    # --- Download ONNX Model ---
    try:
        logger.info("Checking for ONNX Silero VAD model...")
        torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            onnx=True  # Explicitly request the ONNX model
        )
        logger.info("✅ ONNX Silero VAD model is cached.")
    except Exception as e:
        logger.error(f"❌ Failed to download ONNX Silero VAD model: {e}")


if __name__ == '__main__':
    logger.info("--- Starting Model Download and Caching Process ---")
    download_whisper_models()
    print("-" * 20)
    download_silero_vad()
    logger.info("\n--- Model caching process complete. ---")