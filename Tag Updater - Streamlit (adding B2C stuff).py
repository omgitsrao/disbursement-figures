import streamlit as st
import pandas as pd
import os

st.title("Disbursement File Processing Tool")

mode = st.selectbox(
    "Select Processing Mode",
    ["Select an Option", "G2P Disbursements", "BISP / RSU / PSPA"]
)

def read_csv(file):
    try:
        return pd.read_csv(
            file,
            encoding="utf-8",
            on_bad_lines='skip'   # skips problematic rows
        )
    except UnicodeDecodeError:
        return pd.read_csv(
            file,
            encoding="latin1",
            on_bad_lines='skip'
        )

# MODE 1: G2P Disbursements
if mode == "G2P Disbursements":

    detailed_file = st.file_uploader(
        "Upload Detailed G2P CSV File",
        type=["csv"]
    )

    tagging_file = st.file_uploader(
        "Upload Tagging Master File",
        type=["csv"]
    )

    if detailed_file and tagging_file:

        # -----------------------
        # Load Files
        # -----------------------
        detailed_df = read_csv(detailed_file)
        tagging_df = read_csv(tagging_file)

        # -----------------------
        # Standardize ACTITLE
        # -----------------------
        detailed_df["ACTITLE"] = detailed_df["ACTITLE"].astype(str).str.strip().str.upper()
        tagging_df["ACTITLE"] = tagging_df["ACTITLE"].astype(str).str.strip().str.upper()

        # -----------------------
        # Drop duplicates to avoid row multiplication
        # -----------------------
        tagging_df = tagging_df.drop_duplicates(subset=["ACTITLE"])

        # -----------------------
        # Select Required Columns (now includes category_cps)
        # -----------------------
        tagging_subset = tagging_df[
            ["ACTITLE", "COMPANY_TYPE", "CATEGORY", "Region", "category_cps"]
        ].rename(columns={
            "COMPANY_TYPE": "NEW_COMPANY_TYPE",
            "CATEGORY": "NEW_CATEGORY",
            "Region": "NEW_REGION",
            "category_cps": "NEW_CATEGORY_CPS"
        })

        # -----------------------
        # Merge
        # -----------------------
        detailed_df = detailed_df.merge(
            tagging_subset,
            on="ACTITLE",
            how="left"
        )

        # -----------------------
        # Update Only When Match Exists
        # -----------------------
        detailed_df["COMPANY_TYPE"] = detailed_df["NEW_COMPANY_TYPE"].fillna(detailed_df["COMPANY_TYPE"])
        detailed_df["CATEGORY"] = detailed_df["NEW_CATEGORY"].fillna(detailed_df["CATEGORY"])
        detailed_df["REGION"] = detailed_df["NEW_REGION"].fillna(detailed_df["REGION"])
        detailed_df["category_cps"] = detailed_df["NEW_CATEGORY_CPS"].fillna(detailed_df["category_cps"])

        # -----------------------
        # Drop Helper Columns
        # -----------------------
        detailed_df.drop(
            columns=["NEW_COMPANY_TYPE", "NEW_CATEGORY", "NEW_REGION", "NEW_CATEGORY_CPS"],
            inplace=True
        )

        # -----------------------
        # Revenue Calculation
        # -----------------------
        detailed_df["revenue"] = pd.to_numeric(detailed_df["revenue"], errors="coerce").fillna(0)

        b2b_rev = detailed_df[detailed_df["COMPANY_TYPE"] == "B2B"]["revenue"].sum()

        b2g_rev = detailed_df[
            detailed_df["COMPANY_TYPE"].isin(["B2G", "B2G PSPA", "B2G RSU", "B2G BISP"])
        ]["revenue"].sum()

        blank_count = detailed_df["COMPANY_TYPE"].isna().sum()

        # -----------------------
        # Display Summary
        # -----------------------
        st.subheader("📊 G2P Revenue Summary")

        st.write(f"**B2B Revenue:** {b2b_rev:,.2f}")
        st.write(f"**B2G Revenue:** {b2g_rev:,.2f}")
        st.write(f"**Blank COMPANY_TYPE Count:** {blank_count}")

        # -----------------------
        # Export Updated File
        # -----------------------
        base, ext = os.path.splitext(detailed_file.name)
        output_name = base + " - Updated.csv"

        updated_csv = detailed_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Download Updated G2P File",
            data=updated_csv,
            file_name=output_name,
            mime="text/csv"
        )

        st.success("✅ G2P Tagging & Processing Completed Successfully!")


# MODE 2: BISP / RSU / PSPA
elif mode == "BISP / RSU / PSPA":
    files = st.file_uploader(
        "Upload BISP / RSU / PSPA Files",
        type=["csv"],
        accept_multiple_files=True
    )

    if files:
        summary = []

        bisp_total = 0
        pspa_total = 0

        for f in files:
            df = read_csv(f)
            name = f.name.upper()

            # Auto-detect program
            if "PSPA" in name:
                program = "PSPA"
                rev_col = "TOTAL_REVENUE"
            elif "BISP" in name:
                program = "BISP"
                rev_col = "REVENUE"
            else:
                program = "RSU"
                rev_col = "REVENUE"

            # Calculate revenue
            df[rev_col] = pd.to_numeric(df[rev_col], errors='coerce').fillna(0)
            total_rev = df[rev_col].sum()

            # Accumulate program totals
            if program == "BISP":
                bisp_total += total_rev
            elif program == "PSPA":
                pspa_total += total_rev

            summary.append({
                "File": f.name,
                "Program": program,
                "Revenue Column": rev_col,
                "Total Revenue": total_rev
            })

            # Save updated file
            base, ext = os.path.splitext(f.name)
            out_name = base + " - Updated" + ext
            updated_csv = df.to_csv(index=False).encode("utf-8")

            st.download_button(
                f"Download Updated — {out_name}",
                data=updated_csv,
                file_name=out_name,
                mime="text/csv"
            )

        # Summary table
        st.subheader("📊 Program Revenue Summary")
        st.dataframe(pd.DataFrame(summary))

        # Grand total
        grand = sum(s["Total Revenue"] for s in summary)
        st.markdown(f"### 💰 Grand Total: **{grand:,.2f}**")

        # Program totals display
        bisp_pspa_total = bisp_total + pspa_total

        st.markdown("---")
        st.markdown("## 📌 Program Totals")
        st.write(f"**BISP Revenue:** {bisp_total:,.2f}")
        st.write(f"**PSPA Revenue:** {pspa_total:,.2f}")
        st.write(f"**BISP / PSPA Revenue:** {bisp_pspa_total:,.2f}")

        st.success("BISP / RSU / PSPA Processing complete!")