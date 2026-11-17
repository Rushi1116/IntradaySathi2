import os
import tempfile

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["MODEL_DIR"] = tempfile.mkdtemp()
os.environ["LOAD_FULL_UNIVERSE"] = "false"
os.environ["ENFORCE_MARKET_HOURS"] = "false"
