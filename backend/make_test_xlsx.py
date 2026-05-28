"""Phase 5 helper: generate a deterministic sales XLSX with known aggregates,
so spreadsheet reasoning can be verified against ground truth."""

import pandas as pd

REGIONS = ["North", "South", "East", "West"]
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
PRODUCTS = ["Widget", "Gadget", "Gizmo"]


def build(path: str = "sales.xlsx") -> str:
    rows = []
    for ri, region in enumerate(REGIONS):
        for qi, q in enumerate(QUARTERS):
            for pi, product in enumerate(PRODUCTS):
                units = 100 + ri * 30 + qi * 25 + pi * 10
                price = 12 + pi * 8  # Widget 12, Gadget 20, Gizmo 28
                rows.append(
                    {
                        "Region": region,
                        "Quarter": q,
                        "Product": product,
                        "Units": units,
                        "Revenue": round(units * price, 2),
                    }
                )
    df = pd.DataFrame(rows)
    df.to_excel(path, sheet_name="Sales", index=False)
    return df, path


if __name__ == "__main__":
    df, out = build()
    print(f"Wrote {out}: {len(df)} rows")
    print("\n=== GROUND TRUTH ===")
    by_region = df.groupby("Region")["Revenue"].sum().sort_values(ascending=False)
    print("Total revenue by region:\n", by_region.to_string())
    q4 = df[df["Quarter"] == "Q4"].groupby("Region")["Revenue"].sum().sort_values(ascending=False)
    print("\nQ4 revenue by region:\n", q4.to_string())
    print("\nTop region overall:", by_region.index[0], f"({by_region.iloc[0]:.2f})")
    print("Total units of Gizmo:", int(df[df["Product"] == "Gizmo"]["Units"].sum()))
