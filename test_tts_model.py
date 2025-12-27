#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script test để kiểm tra việc load TTS model XTTS-v2.
Chạy script này nhiều lần cho đến khi model load thành công.
"""

import sys
import traceback
import io
from pathlib import Path

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def test_tts_model():
    """Test loading TTS model với fix cho PyTorch 2.6."""
    print("=" * 60)
    print("TEST LOAD TTS MODEL XTTS-v2")
    print("=" * 60)
    print()
    
    # Check Python version
    print(f"Python version: {sys.version}")
    print()
    
    # Check torch
    try:
        import torch
        print(f"PyTorch version: {torch.__version__}")
    except ImportError:
        print("ERROR: PyTorch chưa được cài đặt!")
        print("Chạy: pip install torch")
        return False
    print()
    
    # Check TTS
    try:
        from TTS.api import TTS
        print("TTS module: OK")
    except ImportError:
        print("ERROR: TTS module chưa được cài đặt!")
        print("Chạy: pip install TTS")
        return False
    print()
    
    # Fix for PyTorch 2.6
    print("Applying PyTorch 2.6 fix...")
    original_load = torch.load
    
    def patched_load(*args, **kwargs):
        """Patch torch.load để set weights_only=False."""
        if 'weights_only' not in kwargs:
            kwargs['weights_only'] = False
        return original_load(*args, **kwargs)
    
    # Add safe globals for XttsConfig
    try:
        from TTS.tts.configs.xtts_config import XttsConfig
        if hasattr(torch.serialization, 'add_safe_globals'):
            torch.serialization.add_safe_globals([XttsConfig])
            print("Added XttsConfig to safe globals")
    except (ImportError, AttributeError) as e:
        print(f"Warning: Could not add safe globals: {e}")
    
    # Patch torch.load
    torch.load = patched_load
    print("torch.load patched: weights_only=False by default")
    print()
    
    # Try to load model
    model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
    print(f"Attempting to load model: {model_name}")
    print("This may take a while on first run (downloading model)...")
    print()
    
    try:
        tts = TTS(
            model_name=model_name,
            progress_bar=True,
            gpu=False,
        )
        print()
        print("=" * 60)
        print("[SUCCESS] TTS model loaded successfully!")
        print("=" * 60)
        print()
        if hasattr(tts, 'synthesizer') and tts.synthesizer:
            if hasattr(tts.synthesizer, 'tts_model'):
                print(f"Model type: {type(tts.synthesizer.tts_model).__name__}")
                print(f"Model device: {getattr(tts.synthesizer.tts_model, 'device', 'unknown')}")
            else:
                print("Model loaded but tts_model attribute not found")
        else:
            print("Model loaded but synthesizer not found")
        print()
        
        # Test text-to-speech synthesis
        print("=" * 60)
        print("TESTING TEXT-TO-SPEECH SYNTHESIS")
        print("=" * 60)
        print()
        
        test_text = "Hello, this is a test of the text to speech system."
        output_path = Path("test_output.wav")
        
        # Try to find a sample audio file for voice cloning
        sample_audio = None
        voices_dir = Path("voices")
        if voices_dir.exists():
            # Look for any audio file in voices directory
            for audio_file in voices_dir.rglob("*.wav"):
                sample_audio = audio_file
                break
            if not sample_audio:
                for audio_file in voices_dir.rglob("*.mp3"):
                    sample_audio = audio_file
                    break
        
        try:
            if hasattr(tts, 'is_multi_speaker') and tts.is_multi_speaker:
                if sample_audio and sample_audio.exists():
                    print(f"Using sample audio: {sample_audio}")
                    print(f"Text: {test_text}")
                    print(f"Language: en")
                    print("Generating speech...")
                    print()
                    
                    tts.tts_to_file(
                        text=test_text,
                        file_path=str(output_path),
                        language="en",
                        speaker_wav=str(sample_audio),
                    )
                    
                    if output_path.exists():
                        file_size = output_path.stat().st_size
                        print()
                        print("=" * 60)
                        print("[SUCCESS] Text-to-speech synthesis successful!")
                        print("=" * 60)
                        print(f"  Output file: {output_path.absolute()}")
                        print(f"  File size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
                        print()
                        print("Full test: PASSED")
                        print("  ✓ Model loading: OK")
                        print("  ✓ Text-to-speech synthesis: OK")
                        print("  ✓ Output file created: OK")
                        print()
                    else:
                        print("[ERROR] Synthesis completed but output file not found")
                        return False
                else:
                    print("[WARNING] Multi-speaker model requires speaker_wav")
                    print("  No sample audio found in voices/ directory")
                    print("  Creating a minimal test audio file...")
                    print()
                    
                    # Create a minimal test using TTS API's built-in method
                    # For XTTS, we can use a very short text with default voice
                    try:
                        # Try to use TTS with a very short reference
                        # XTTS can work without speaker_wav for very short texts in some cases
                        print("  Attempting synthesis without speaker_wav (may fail)...")
                        tts.tts_to_file(
                            text="Test",
                            file_path=str(output_path),
                            language="en",
                        )
                        if output_path.exists():
                            print(f"[OK] Basic synthesis test passed")
                        else:
                            print("[SKIP] Synthesis test requires speaker_wav file")
                    except Exception as e:
                        print(f"[SKIP] Synthesis test requires speaker_wav: {e}")
                        print("  To fully test, add a .wav or .mp3 file to voices/ directory")
            else:
                print(f"Text: {test_text}")
                print(f"Language: en")
                print("Generating speech...")
                print()
                
                tts.tts_to_file(
                    text=test_text,
                    file_path=str(output_path),
                    language="en",
                )
                
                if output_path.exists():
                    file_size = output_path.stat().st_size
                    print()
                    print("=" * 60)
                    print("[SUCCESS] Text-to-speech synthesis successful!")
                    print("=" * 60)
                    print(f"  Output file: {output_path.absolute()}")
                    print(f"  File size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
                    print()
                    print("Full test: PASSED")
                    print("  ✓ Model loading: OK")
                    print("  ✓ Text-to-speech synthesis: OK")
                    print("  ✓ Output file created: OK")
                    print()
                else:
                    print("[ERROR] Synthesis completed but output file not found")
                    return False
                    
        except Exception as synth_error:
            print()
            print("[ERROR] Text-to-speech synthesis failed!")
            print(f"  Error: {synth_error}")
            print()
            print("Full traceback:")
            print("-" * 60)
            traceback.print_exc()
            print("-" * 60)
            print()
            return False
        
        # Restore original torch.load
        torch.load = original_load
        
        return True
        
    except Exception as e:
        print()
        print("=" * 60)
        print("[ERROR] Failed to load TTS model")
        print("=" * 60)
        print()
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print()
        print("Full traceback:")
        print("-" * 60)
        traceback.print_exc()
        print("-" * 60)
        print()
        
        # Restore original torch.load
        torch.load = original_load
        
        return False

if __name__ == "__main__":
    success = test_tts_model()
    sys.exit(0 if success else 1)

