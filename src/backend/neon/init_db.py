import pandas as pd
from sqlalchemy import create_engine
from pathlib import Path

# Paste the string you copied in Step 2 here
SECRETS_FILE: Path = Path("../secrets/passwords/neon.txt")
NEON_URL: str = SECRETS_FILE.read_text(encoding="utf-8").strip()

# Load your 1.5 GB file
df = pd.read_csv("../data/nutrients/food_nutrients.csv")

# This creates the database connection
engine = create_engine(NEON_URL)

# This pushes the data. It will create all 79 columns for you.
# Note: If your file is over 0.5 GB, this will likely error out when it hits the limit.
df.to_sql("food_data", engine, if_exists="replace", index=False)

print("Finished!")
