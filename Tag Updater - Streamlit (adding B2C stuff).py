import streamlit as st
import pandas as pd
import os

st.title("Disbursement File Processing Tool")

mode = st.selectbox(
    "Select Processing Mode",
    ["Select an Option", "G2P Disbursements", "BISP / PSPA / RSU / MKB / KP Ramzan"]
)

def read_csv(file):
    try:
        return pd.read_csv(file, encoding="utf-8-sig", on_bad_lines='skip')
    except UnicodeDecodeError:
        file.seek(0)
        return pd.read_csv(file, encoding="latin1", on_bad_lines='skip')

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

        b2g_categories = ["Social Services", "Education", "Humanitarian Aid", "Healthcare", "Cultural Heritage"]
        b2g_rev = detailed_df[
            detailed_df["CATEGORY"].isin(b2g_categories)
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


elif mode == "BISP / PSPA / RSU / MKB / KP Ramzan":
    files = st.file_uploader(
        "Upload Program Files (BISP, PSPA, RSU, MKB, KP Ramzan)",
        type=["csv"],
        accept_multiple_files=True
    )
 
    PROGRAM_CONFIG = {
        "BISP": {
            "revenue_col":     "REVENUE",
            "disb_amt_col":    None,
            "disb_txn_col":    None,
            "collect_amt_col": "total_amt",
            "collect_txn_col": "total_transactions",
        },
        "PSPA": {
            "revenue_col":     "TOTAL_REVENUE",
            "disb_amt_col":    None,
            "disb_txn_col":    None,
            "collect_amt_col": "TRXAMT",
            "collect_txn_col": "NO_OF_TRANSACTIONS",
        },
        "RSU": {
            "revenue_col":     "REVENUE",
            "disb_amt_col":    None,
            "disb_txn_col":    None,
            "collect_amt_col": "DISBURSMENT_AMOUNT",
            "collect_txn_col": "NO_OF_TRANSACTIONS",
        },
        "MKB": {
            "revenue_col":     "REVENUE",
            "disb_amt_col":    "DISBURSMENT_AMOUNT",
            "disb_txn_col":    "NO_OF_TRANSACTIONS_DISBURSMENT",
            "collect_amt_col": "WITHDRAW_AMOUNT",
            "collect_txn_col": "NO_OF_TRANSACTIONS_COLLECTED",
        },
        "KPRAMZAN": {
            "revenue_col":     "REVENUE",
            "disb_amt_col":    "DISBURSMENT_AMOUNT",
            "disb_txn_col":    "NO_OF_TRANSACTIONS_DISBURSMENT",
            "collect_amt_col": "WITHDRAW_AMOUNT",
            "collect_txn_col": "NO_OF_TRANSACTIONS_COLLECTED",
        },
    }
 
    def detect_program(filename):
        name = filename.upper().replace(" ", "").replace("_", "").replace("-", "")
        if "KPRAMZAN" in name or "RAMZAN" in name:
            return "KPRAMZAN"
        if "PSPA" in name:
            return "PSPA"
        if "BISP" in name:
            return "BISP"
        if "MKB" in name:
            return "MKB"
        if "RSU" in name:
            return "RSU"
        return None
 
    def safe_sum(df, col):
        if col and col in df.columns:
            return pd.to_numeric(df[col], errors="coerce").fillna(0).sum()
        return None
 
    def format_copyable_row(disb_txn, disb_amt, collect_txn, collect_amt, revenue):
        """Returns a tab-separated row in column order:
        Disbursement Transactions | Disbursement Amount | Collected Transactions | Collected Amount | Revenue
        """
        def fmt_txn(val):
            return f"{int(val):,}" if val is not None else "0"
        def fmt_amt(val):
            return f"{val:,.2f}" if val is not None else "0.00"
 
        return "\t".join([
            fmt_txn(disb_txn),
            fmt_amt(disb_amt),
            fmt_txn(collect_txn),
            fmt_amt(collect_amt),
            fmt_amt(revenue),
        ])
 
    if files:
        for f in files:
            df = read_csv(f)
            program = detect_program(f.name)
 
            if not program:
                st.warning(f"⚠️ Could not detect program for **{f.name}** — skipping.")
                continue
 
            cfg = PROGRAM_CONFIG[program]
 
            revenue     = safe_sum(df, cfg["revenue_col"]) or 0
            disb_amt    = safe_sum(df, cfg["disb_amt_col"])
            disb_txn    = safe_sum(df, cfg["disb_txn_col"])
            collect_amt = safe_sum(df, cfg["collect_amt_col"])
            collect_txn = safe_sum(df, cfg["collect_txn_col"])
 
            # ----------------------------
            # Per-file display
            # ----------------------------
            st.markdown(f"### 📄 {f.name} — `{program}`")
 
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Disb. Transactions", f"{int(disb_txn):,}"    if disb_txn    is not None else "—")
            col2.metric("Disb. Amount",        f"{disb_amt:,.2f}"     if disb_amt    is not None else "—")
            col3.metric("Collect Txns",        f"{int(collect_txn):,}" if collect_txn is not None else "—")
            col4.metric("Collect Amount",      f"{collect_amt:,.2f}"  if collect_amt is not None else "—")
            col5.metric("Revenue",             f"{revenue:,.2f}")
 
            # Copyable tab-separated row
            st.caption("📋 Copy row (paste directly into Excel 'CTRL+SHIFT+V'):")
            copyable = format_copyable_row(disb_txn, disb_amt, collect_txn, collect_amt, revenue)
            st.code(copyable, language=None)
 
            st.markdown("---")
 
            # Download button
            base, ext = os.path.splitext(f.name)
            out_name = base + " - Updated" + ext
            st.download_button(
                f"⬇️ Download — {out_name}",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name=out_name,
                mime="text/csv"
            )
 
        st.success("✅ All program files processed successfully!")
