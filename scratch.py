import pandas as pd

path = "tests/nh_test.csv"  # adjust if needed
df = pd.read_csv(path, dtype=str)

print("Shape:", df.shape)
print("\nColumns:")
print(df.columns.tolist())

print("\nSample rows that might be duplicates (first 30 rows):")
print(df.head(30))

# check normalized comparison
df_norm = df.applymap(lambda x: str(x).strip().upper() if pd.notna(x) else "")
dup_mask = df_norm.duplicated(keep=False)
print("\nDuplicate rows detected by normalization:", dup_mask.sum())

if dup_mask.sum() > 0:
    print("\nRows flagged as duplicates:")
    print(df.loc[dup_mask])
