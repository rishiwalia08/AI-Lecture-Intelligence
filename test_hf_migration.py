"""
test_hf_migration.py
====================
Validate Hugging Face API integration and test cloud-readiness.

Usage:
    python test_hf_migration.py
    python test_hf_migration.py --skip-api  # Test without API call
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.logger import get_logger

logger = get_logger(__name__)


def test_imports():
    """Test that all required imports work."""
    logger.info("=" * 60)
    logger.info("TEST 1: Import Validation")
    logger.info("=" * 60)

    try:
        from src.llm.hf_client import HFClient
        logger.info("✅ HFClient imported")
    except Exception as e:
        logger.error(f"❌ HFClient import failed: {e}")
        return False

    try:
        from src.llm.llm_loader import HuggingFaceProvider, LLMConfig, load_llm
        logger.info("✅ HuggingFaceProvider imported")
        logger.info("✅ LLMConfig imported")
        logger.info("✅ load_llm imported")
    except Exception as e:
        logger.error(f"❌ Loader imports failed: {e}")
        return False

    try:
        import huggingface_hub
        logger.info("✅ huggingface_hub library available")
    except ImportError:
        logger.error("❌ huggingface_hub not installed. Run: pip install huggingface_hub")
        return False

    return True


def test_config():
    """Test configuration loading."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Configuration Loading")
    logger.info("=" * 60)

    try:
        import yaml
        from src.llm.llm_loader import LLMConfig

        config_path = project_root / "config" / "config.yaml"
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        llm_config = config.get("llm", {})
        provider = llm_config.get("provider", "")
        model = llm_config.get("model", "")

        logger.info(f"Provider: {provider}")
        logger.info(f"Model: {model}")

        if provider != "huggingface":
            logger.warning(f"⚠️  Expected provider='huggingface', got '{provider}'")

        if "mistral" not in model.lower():
            logger.warning(f"⚠️  Expected Mistral model, got '{model}'")

        logger.info("✅ Config loaded successfully")
        return True

    except Exception as e:
        logger.error(f"❌ Config loading failed: {e}")
        return False


def test_api_key():
    """Test that API key is available."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: API Key Availability")
    logger.info("=" * 60)

    api_key = os.getenv("HF_API_KEY")

    if not api_key:
        logger.warning("⚠️  HF_API_KEY not set")
        logger.info("\nTo set API key:")
        logger.info("  1. Get token: https://huggingface.co/settings/tokens")
        logger.info("  2. Export: export HF_API_KEY='hf_your_token_here'")
        logger.info("  3. Or add to .env file")
        return False

    # Mask the key for security
    masked = api_key[:10] + "..." + api_key[-5:]
    logger.info(f"✅ API key found: {masked}")
    return True


def test_llm_loading(skip_api=False):
    """Test LLM provider loading."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: LLM Provider Loading")
    logger.info("=" * 60)

    if skip_api:
        logger.info("⏭️  Skipping API test (--skip-api)")
        return True

    try:
        from src.llm.llm_loader import LLMConfig, load_llm

        # Test HuggingFace provider
        config = LLMConfig(provider="huggingface")
        logger.info(f"Loading provider: {config.provider}")
        logger.info(f"Model: {config.model}")

        llm = load_llm(config)
        logger.info(f"✅ Provider loaded: {type(llm).__name__}")

        # Test simple message generation
        logger.info("\nTesting API connection...")
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello in one word."},
        ]

        response = llm.generate(messages)
        logger.info(f"✅ API response received: {response.content[:50]}...")
        logger.info(f"   Tokens: in={response.input_tokens}, out={response.output_tokens}")
        logger.info(f"   Latency: {response.latency_s:.2f}s")

        return True

    except ValueError as e:
        if "API key" in str(e):
            logger.warning(f"⚠️  {e}")
            return False
        logger.error(f"❌ {e}")
        return False
    except Exception as e:
        logger.error(f"❌ LLM loading failed: {e}")
        return False


def test_answer_generator():
    """Test answer generation with HF provider."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: Answer Generator")
    logger.info("=" * 60)

    try:
        from src.llm.llm_loader import LLMConfig, load_llm
        from src.llm.answer_generator import AnswerGenerator

        config = LLMConfig(provider="huggingface")
        llm = load_llm(config)

        generator = AnswerGenerator(llm)
        logger.info("✅ AnswerGenerator initialized")

        # Test with sample chunks
        sample_chunks = [
            {
                "text": "Backpropagation is an algorithm for training neural networks.",
                "lecture_id": "lecture_01",
                "start_time": 120,
                "end_time": 130,
            }
        ]

        result = generator.generate(
            query="What is backpropagation?",
            chunks=sample_chunks,
        )

        logger.info(f"✅ Answer generated: {result.answer[:80]}...")
        logger.info(f"   Sources: {len(result.sources)}")
        logger.info(f"   Grounded: {result.grounded}")

        return True

    except Exception as e:
        logger.error(f"❌ Answer generation failed: {e}")
        return False


def test_education_modules():
    """Test education modules (flashcards, summaries) work with HF."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 6: Education Modules")
    logger.info("=" * 60)

    try:
        from src.llm.llm_loader import LLMConfig, load_llm
        from src.education.flashcard_generator import FlashcardGenerator
        from src.education.lecture_summarizer import LectureSummarizer

        config = LLMConfig(provider="huggingface")
        llm = load_llm(config)

        # Test flashcard generator
        try:
            fg = FlashcardGenerator(llm)
            logger.info("✅ FlashcardGenerator initialized with HF")
        except Exception as e:
            logger.error(f"❌ FlashcardGenerator failed: {e}")
            return False

        # Test lecture summarizer
        try:
            ls = LectureSummarizer(llm)
            logger.info("✅ LectureSummarizer initialized with HF")
        except Exception as e:
            logger.error(f"❌ LectureSummarizer failed: {e}")
            return False

        return True

    except Exception as e:
        logger.error(f"❌ Education module test failed: {e}")
        return False


def test_dependencies():
    """Test all required dependencies."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 7: Dependency Check")
    logger.info("=" * 60)

    required = {
        "huggingface_hub": "Hugging Face Inference API",
        "groq": "Groq API (optional fallback)",
        "pydantic": "Data validation",
        "torch": "PyTorch",
        "transformers": "Transformer models",
        "chromadb": "Vector database",
    }

    all_ok = True
    for package, description in required.items():
        try:
            __import__(package)
            logger.info(f"✅ {package}: {description}")
        except ImportError:
            required_for = "Required" if package in ["huggingface_hub", "pydantic"] else "Optional"
            logger.warning(f"⚠️  {package}: {description} ({required_for})")
            if required_for == "Required":
                all_ok = False

    return all_ok


def main():
    """Run all tests."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate HF migration")
    parser.add_argument("--skip-api", action="store_true", help="Skip API tests")
    args = parser.parse_args()

    logger.info("\n" + "🚀" * 30)
    logger.info("HUGGING FACE MIGRATION VALIDATION")
    logger.info("🚀" * 30)

    results = {
        "Imports": test_imports(),
        "Config": test_config(),
        "API Key": test_api_key(),
        "Dependencies": test_dependencies(),
    }

    if not args.skip_api and results["API Key"]:
        results["LLM Loading"] = test_llm_loading(skip_api=False)
        # Only run these if API key is available
        results["Answer Generator"] = test_answer_generator()
        results["Education Modules"] = test_education_modules()

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_flag in results.items():
        status = "✅ PASS" if passed_flag else "❌ FAIL"
        logger.info(f"{status}: {test_name}")

    logger.info(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        logger.info("\n✨ All tests passed! Ready for cloud deployment.")
        return 0
    else:
        logger.warning("\n⚠️  Some tests failed. Check configuration.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
