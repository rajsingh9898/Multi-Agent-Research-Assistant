import os
import sys
import logging
from dotenv import load_dotenv

# Load local .env file if present for testing/dev environments
load_dotenv()

# Configure startup check logging to display clear, readable steps
logging.basicConfig(level=logging.INFO, format="%(levelname)s:startup: %(message)s")
logger = logging.getLogger("startup")

REQUIRED_VARS = [
    ("OPENAI_API_KEY", "sk-", "OpenAI API key"),
    ("TAVILY_API_KEY", "tvly-", "Tavily search key"),
    ("PINECONE_API_KEY", None, "Pinecone vector DB key"),
    ("PINECONE_INDEX_NAME", None, "Pinecone index name"),
    ("FIREBASE_PROJECT_ID", None, "Firebase project ID"),
    ("FIREBASE_PRIVATE_KEY", "-----BEGIN", "Firebase private key"),
    ("FIREBASE_CLIENT_EMAIL", "@", "Firebase service account email"),
    ("FIREBASE_STORAGE_BUCKET", None, "Firebase storage bucket")
]

OPTIONAL_VARS = [
    ("PINECONE_INDEX_HOST", "Pinecone host URL"),
    ("BACKEND_URL", "Backend URL for CORS"),
    ("FRONTEND_URL", "Frontend URL for CORS")
]


def check_required_vars() -> bool:
    """Verifies that all required environment variables are set and conform to format requirements."""
    logger.info("🔍 Checking required environment variables...")
    all_ok = True

    for var_name, prefix, description in REQUIRED_VARS:
        value = os.getenv(var_name, "")
        
        if not value:
            logger.error(f"❌ MISSING: {var_name} ({description})")
            all_ok = False
        elif prefix and not value.startswith(prefix):
            # Key has a mismatching prefix
            logger.warning(f"⚠️  {var_name} may be malformed")
            logger.warning(f"   Expected to start with: '{prefix}'")
            logger.warning(f"   Got: '{value[:20]}...'")
        else:
            # Mask key value safely for output log preview
            if len(value) > 20:
                preview = value[:8] + "..." + value[-4:]
            else:
                preview = value[:4] + "..."
            logger.info(f"✅ {var_name}: {preview}")

    return all_ok


def check_optional_vars():
    """Outputs information about optional environment configuration options."""
    logger.info("🔍 Checking optional environment variables...")

    for var_name, description in OPTIONAL_VARS:
        value = os.getenv(var_name, "")
        if value:
            logger.info(f"✅ {var_name}: set")
        else:
            logger.warning(f"⚠️  {var_name}: not set ({description}) - using defaults")


def check_firebase_key() -> bool:
    """Validates the format of the FIREBASE_PRIVATE_KEY environment variable."""
    key = os.getenv("FIREBASE_PRIVATE_KEY", "")

    if not key:
        # Caught by check_required_vars, avoid double reporting
        return True

    issues = []

    if "\\n" in key and "-----BEGIN" in key:
        issues.append("Key has escaped \\n - will be auto-fixed by config parser")

    if not key.strip().startswith("-----BEGIN"):
        issues.append("Key doesn't start with '-----BEGIN'")

    if "PRIVATE KEY" not in key:
        issues.append("Key doesn't contain 'PRIVATE KEY' substring")

    if issues:
        for issue in issues:
            logger.warning(f"⚠️  Firebase key format issue: {issue}")
    else:
        logger.info("✅ Firebase private key: valid format")

    return True  # Issues are warnings, not fatal blockages here


def check_fonts() -> bool:
    """Verifies that the DejaVu font assets needed for PDF rendering exist and have valid sizes."""
    logger.info("🔍 Checking PDF font files...")

    # Check /app/assets/fonts (production container) or fall back to local relative path
    font_dir = "/app/assets/fonts"
    if not os.path.exists(font_dir):
        font_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets", "fonts"))

    fonts_needed = [
        "DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf"
    ]

    if not os.path.exists(font_dir):
        logger.warning(f"⚠️  Font directory not found: {font_dir}")
        logger.warning("   PDF export will fall back to default Helvetica fonts.")
        return True  # Fallback exists, not a fatal crash


    for font in fonts_needed:
        font_path = os.path.join(font_dir, font)
        if os.path.exists(font_path):
            size = os.path.getsize(font_path)
            logger.info(f"✅ {font}: {size:,} bytes")
        else:
            logger.warning(f"⚠️  {font}: not found")
            logger.warning("   PDF will fall back to Helvetica for this font weight.")

    return True


def check_python_imports() -> bool:
    """Validates import availability of critical Python modules in the environment."""
    logger.info("🔍 Checking critical Python imports...")

    imports_to_check = [
        ("fastapi", "FastAPI framework"),
        ("openai", "OpenAI client"),
        ("pinecone", "Pinecone vector DB"),
        ("tavily", "Tavily search"),
        ("firebase_admin", "Firebase Admin SDK"),
        ("reportlab", "PDF generation"),
        ("langchain", "LangChain framework")
    ]

    all_ok = True
    for module, description in imports_to_check:
        try:
            __import__(module)
            logger.info(f"✅ {module}: importable")
        except ImportError as e:
            logger.error(f"❌ {module}: IMPORT ERROR - {e}")
            logger.error(f"   Missing package dependency in environment.")
            all_ok = False

    return all_ok


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("STARTUP VALIDATION")
    logger.info("Multi-Agent Research Assistant")
    logger.info("=" * 50)

    check_optional_vars()

    checks = [
        ("Required env vars", check_required_vars),
        ("Firebase key format", check_firebase_key),
        ("Font files", check_fonts),
        ("Python imports", check_python_imports)
    ]

    failed = []
    for name, check_fn in checks:
        try:
            result = check_fn()
            if not result:
                failed.append(name)
        except Exception as e:
            logger.error(f"Check '{name}' threw exception: {e}")
            failed.append(name)

    if failed:
        logger.error("\n" + "=" * 50)
        logger.error("❌ STARTUP FAILED")
        logger.error(f"Failed checks: {failed}")
        logger.error("Fix the configuration or environment issues and restart.")
        logger.error("=" * 50)
        sys.exit(1)
    else:
        logger.info("\n" + "=" * 50)
        logger.info("✅ ALL STARTUP CHECKS PASSED")
        logger.info("Starting FastAPI server...")
        logger.info("=" * 50 + "\n")
        sys.exit(0)
