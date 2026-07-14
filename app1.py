import os
import re
import json
import sqlite3
import datetime
import pandas as pd
import streamlit as st


# 1. SIMPLE MAPPING & CLINICAL SETTINGS

# Dict lookup to standardize variant lab spelling inputs
TEST_MAPPINGS = {
    "haemoglobin": "Hemoglobin", 
    "haemoglobin (whole blood/photometric method)": "Hemoglobin",
    "hemoglobin": "Hemoglobin", 
    "aemoglobin": "Hemoglobin", 
    "hb": "Hemoglobin", 
    "hgb": "Hemoglobin",
    "total leucocyte count (tlc)": "WBC_Count", 
    "total leucocyte count (tlc) (whole blood/impedence method)": "WBC_Count",
    "total wbc count": "WBC_Count", 
    "wbc count": "WBC_Count", 
    "tal wbc count": "WBC_Count",
    "serum creatinine": "Serum_Creatinine", 
    "creatinine, serum": "Serum_Creatinine", 
    "sr creatinine": "Serum_Creatinine",
    "creatinine": "Serum_Creatinine",
    "sodium": "Sodium", 
    "sodium (na+)": "Sodium", 
    "na+": "Sodium",
    "potassium": "Potassium", 
    "potassium (k+)": "Potassium", 
    "k+": "Potassium"
}

LIMITS = {
    "Hemoglobin": {"low": 12.0, "high": 16.0, "outlier_low": 2.0, "outlier_high": 25.0, "unit": "g/dL"},
    "WBC_Count": {"low": 4000.0, "high": 10000.0, "outlier_low": 500.0, "outlier_high": 100000.0, "unit": "cells/cu.mm"},
    "Serum_Creatinine": {"low": 0.5, "high": 1.4, "outlier_low": 0.1, "outlier_high": 10.0, "unit": "mg/dL"},
    "Sodium": {"low": 135.0, "high": 145.0, "outlier_low": 100.0, "outlier_high": 180.0, "unit": "mmol/L"},
    "Potassium": {"low": 3.5, "high": 5.1, "outlier_low": 1.5, "outlier_high": 8.0, "unit": "mmol/L"}
}


# 2. RAW MOCK DATA GENERATOR


def create_mock_files():
    os.makedirs("sample_data", exist_ok=True)
    mock_samples = {
        "sample1.json": {
            "traceId": "8435a58fbea9d4d88f3ec7ebba8504fb",
            "statusCode": 200,
            "message": ["Success"],
            "data": {
                "documentId": "DOC001_DISCHARGE_ONLY",
                "correlationId": "corr_001",
                "responseDetails": [{
                    "classifier": "discharge_summary",
                    "data": {
                        "patientName": "John Doe",
                        "admissionDate": "09-10-2025",
                        "hospitalName": "Fortis Hospital",
                        "gender": "Male",
                        "age": "45"
                    }
                }]
            }
        },
        "sample2.json": {
            "traceId": "d6edfe98d7eff4e3eead5c782b06ea3b",
            "statusCode": 200,
            "message": ["Success"],
            "data": {
                "documentId": "DOC002_MESSY_LAB",
                "correlationId": "corr_002",
                "responseDetails": [{
                    "classifier": "lab_report",
                    "data": {
                        "basic_info": {
                            "patient_name": "Jane Smith",
                            "reports_date": "04-10-2025",
                            "lab_or_hospital_name": "Veritas Diagnostics"
                        },
                        "report_details": [
                            {"test_name": "aemoglobin", "result": "9.5", "unit": "g/dl"},
                            {"test_name": "tal WBC Count", "result": "5.45", "unit": "mil/cu.mm"},
                            {"test_name": "Serum Creatinine", "result": "1.1", "unit": "mg/dL"}
                        ]
                    }
                }]
            }
        },
        "sample3.json": {
            "traceId": "ad717d432afa08f2b59bd1bdcb861863",
            "statusCode": 200,
            "message": ["Success"],
            "data": {
                "documentId": "DOC002_MESSY_LAB",
                "correlationId": "corr_003",
                "responseDetails": [{"classifier": "lab_report", "data": {"basic_info": {"patient_name": "Jane Smith"}}}]
            }
        },
        "sample4.json": {
            "traceId": "73659e05dc8768bb034da1029ff89dad",
            "statusCode": 200,
            "message": ["Success"],
            "data": {
                "documentId": "DOC004_TEXT_UNITS",
                "correlationId": "corr_004",
                "responseDetails": [{
                    "classifier": "lab_report",
                    "data": {
                        "basic_info": {
                            "patient_name": "Alice Green",
                            "reports_date": "10/Oct/2025",
                            "lab_or_hospital_name": "Metro Labs"
                        },
                        "report_details": [
                            {"test_name": "HAEMOGLOBIN", "result": "13.7 g/dl", "unit": "g/dl"},
                            {"test_name": "TOTAL LEUCOCYTE COUNT (TLC)", "result": "4,290 cells/cu.mm", "unit": "cells/cu.mm"},
                            {"test_name": "Sodium", "result": "132", "unit": "mmol/L"}
                        ]
                    }
                }]
            }
        },
        "sample5.json": {
            "traceId": "bc7b8b01a14eb62af3ce120c670e5b77",
            "statusCode": 200,
            "message": ["Success"],
            "data": {
                "documentId": "DOC005_OUTLIERS",
                "correlationId": "corr_005",
                "responseDetails": [{
                    "classifier": "lab_report",
                    "data": {
                        "basic_info": {
                            "patient_name": "Bob Brown",
                            "reports_date": "12-10-2025",
                            "lab_or_hospital_name": "Apex Clinic"
                        },
                        "report_details": [
                            {"test_name": "Hb", "result": "1.5", "unit": "g/dl"},
                            {"test_name": "WBC COUNT", "result": "120000", "unit": "cells/cu.mm"},
                            {"test_name": "Potassium (K+)", "result": "6.2", "unit": "mmol/L"}
                        ]
                    }
                }]
            }
        }
    }
    for filename, data in mock_samples.items():
        with open(os.path.join("sample_data", filename), "w") as f:
            json.dump(data, f, indent=2)


# 3. CORE PROCESSING LOGIC (FR-2 & FR-3)


def clean_value(raw_val, test_name):
    if raw_val is None:
        return None
    str_val = str(raw_val).strip().lower()
    if str_val in ["positive", "negative", "absent", "present", "nil"]:
        return None
    str_val = str_val.replace(",", "")
    matches = re.findall(r"\d+\.\d+|\d+", str_val)
    if not matches:
        return None
    try:
        val = float(matches.pop(0))
    except (ValueError, IndexError):
        return None
    if test_name == "WBC_Count" and val < 50.0:
        val = val * 1000.0
    return val

def run_range_validation(val, test_name):
    if val is None:
        return "N/A"
    rules = LIMITS[test_name]
    if val <= rules["outlier_low"] or val >= rules["outlier_high"]:
        return "Outlier"
    elif val < rules["low"]:
        return "Below Range"
    elif val > rules["high"]:
        return "Above Range"
    else:
        return "Within Range"


# 4. DATABASE INITIALIZER (FR-4.1)


def init_db():
    conn = sqlite3.connect("veritas_claims.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS records (
        document_id TEXT PRIMARY KEY,
        patient_name TEXT,
        hospital_name TEXT,
        reports_date TEXT,
        trace_id TEXT,
        correlation_id TEXT,
        ingested_at TEXT,
        status TEXT,
        raw_payload TEXT,
        Hemoglobin_Result REAL, Hemoglobin_Analytics TEXT,
        WBC_Count_Result REAL, WBC_Count_Analytics TEXT,
        Serum_Creatinine_Result REAL, Serum_Creatinine_Analytics TEXT,
        Sodium_Result REAL, Sodium_Analytics TEXT,
        Potassium_Result REAL, Potassium_Analytics TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS run_history (
        timestamp TEXT, files_found INTEGER, ingested INTEGER, duplicates INTEGER, outliers INTEGER
    )
    """)
    conn.commit()
    conn.close()


# 5. PIPELINE INGESTION LOGIC (FR-1)


def run_pipeline():
    init_db()
    create_mock_files()
    
    conn = sqlite3.connect("veritas_claims.db")
    cursor = conn.cursor()
    
    folder = "sample_data"
    if not os.path.exists(folder):
        return
    files = os.listdir(folder)
    
    ingested_count = 0
    duplicate_count = 0
    outliers_count = 0
    
    for f_name in files:
        if not f_name.lower().endswith(".json"):
            continue
            
        file_path = os.path.join(folder, f_name)
        with open(file_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
            
        doc_id = payload.get("data", {}).get("documentId") or payload.get("documentId") or "UNKNOWN"
        corr_id = payload.get("data", {}).get("correlationId") or payload.get("correlationId") or ""
        trace_id = payload.get("traceId") or ""
        
        cursor.execute("SELECT 1 FROM records WHERE document_id = ?", (doc_id,))
        if cursor.fetchone():
            duplicate_count += 1
            continue
            
        patient_name = "Patient Redacted"
        hospital_name = "Hospital Redacted"
        reports_date = "N/A"
        raw_tests = []
        
        details = payload.get("data", {}).get("responseDetails", [])
        if not isinstance(details, list):
            details = [details]
            
        for detail in details:
            classifier = detail.get("classifier", "")
            inner_data = detail.get("data", {})
            if classifier == "discharge_summary":
                patient_name = inner_data.get("patientName") or patient_name
                hospital_name = inner_data.get("hospitalName") or hospital_name
                reports_date = inner_data.get("admissionDate") or reports_date
            elif classifier == "lab_report":
                basic = inner_data.get("basic_info", {})
                patient_name = basic.get("patient_name") or patient_name
                hospital_name = basic.get("lab_or_hospital_name") or hospital_name
                reports_date = basic.get("reports_date") or reports_date
                raw_tests = inner_data.get("report_details", [])
                
        row_data = {
            "document_id": doc_id, "patient_name": patient_name, "hospital_name": hospital_name,
            "reports_date": reports_date, "trace_id": trace_id, "correlation_id": corr_id,
            "ingested_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "status": "PROCESSED",
            "raw_payload": json.dumps(payload),
            "Hemoglobin_Result": None, "Hemoglobin_Analytics": "N/A",
            "WBC_Count_Result": None, "WBC_Count_Analytics": "N/A",
            "Serum_Creatinine_Result": None, "Serum_Creatinine_Analytics": "N/A",
            "Sodium_Result": None, "Sodium_Analytics": "N/A",
            "Potassium_Result": None, "Potassium_Analytics": "N/A"
        }
        
        for t in raw_tests:
            raw_name = t.get("test_name", "")
            canonical_name = TEST_MAPPINGS.get(raw_name.strip().lower())
            if canonical_name:
                cleaned_num = clean_value(t.get("result"), canonical_name)
                analytics_label = run_range_validation(cleaned_num, canonical_name)
                if analytics_label == "Outlier":
                    outliers_count += 1
                row_data[f"{canonical_name}_Result"] = cleaned_num
                row_data[f"{canonical_name}_Analytics"] = analytics_label
                
        cursor.execute("""
        INSERT INTO records (
            document_id, patient_name, hospital_name, reports_date, trace_id, correlation_id, ingested_at, status, raw_payload,
            Hemoglobin_Result, Hemoglobin_Analytics,
            WBC_Count_Result, WBC_Count_Analytics,
            Serum_Creatinine_Result, Serum_Creatinine_Analytics,
            Sodium_Result, Sodium_Analytics,
            Potassium_Result, Potassium_Analytics
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row_data["document_id"], row_data["patient_name"], row_data["hospital_name"], row_data["reports_date"],
            row_data["trace_id"], row_data["correlation_id"], row_data["ingested_at"], row_data["status"], row_data["raw_payload"],
            row_data["Hemoglobin_Result"], row_data["Hemoglobin_Analytics"],
            row_data["WBC_Count_Result"], row_data["WBC_Count_Analytics"],
            row_data["Serum_Creatinine_Result"], row_data["Serum_Creatinine_Analytics"],
            row_data["Sodium_Result"], row_data["Sodium_Analytics"],
            row_data["Potassium_Result"], row_data["Potassium_Analytics"]
        ))
        ingested_count += 1
        
    if len(files) > 0:
        cursor.execute("INSERT INTO run_history VALUES (?, ?, ?, ?, ?)", (
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), len(files), ingested_count, duplicate_count, outliers_count
        ))
    conn.commit()
    conn.close()


# 6. SIMPLE STREAMLIT USER INTERFACE (FR-5)


def main():
    
    # 0. HIDE ALL STREAMLIT SYSTEM STUFF (DEPLOY, SETTINGS, LIGHT/DARK)
   
    st.markdown("""
        <style>
        /* Hides the entire top header containing the Deploy button and settings menu */
        header[data-testid="stHeader"] {
            display: none !important;
        }
        /* Hides the 'Made with Streamlit' footer at the bottom */
        footer {
            visibility: hidden !important;
        }
        /* Hides the sidebar header if any */
        [data-testid="stSidebarHeader"] {
            display: none !important;
        }
        </style>
    """, unsafe_allow_html=True)

    
    # 1. PAGE TITLE & INITIAL DB LOAD
    
    st.title(" Veritas Claims Portal")
    st.write("A simple local dashboard built using SQLite and Python.")
    
    # Always make sure DB exists
    init_db()
    
    # Simple Operations Run controller
    st.sidebar.header("Operations")
    if st.sidebar.button("Run Processing Pipeline ", use_container_width=True):
        with st.spinner("Processing files..."):
            run_pipeline()
        st.sidebar.success("Ingestion successful!")
        
    # Query database records
    conn = sqlite3.connect("veritas_claims.db")
    df_records = pd.read_sql_query("SELECT * FROM records", conn)
    df_history = pd.read_sql_query("SELECT * FROM run_history", conn)
    conn.close()
    
    
    # 2. INGESTION STATISTICS CARDS (FR-5.1)
    
    st.subheader("Ingestion Statistics")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Records Processed", value=len(df_records))
    with col2:
        st.metric(label="Total Executions", value=len(df_history))
    with col3:
        total_dups = int(df_history["duplicates"].sum()) if not df_history.empty else 0
        st.metric(label="Duplicates Blocked", value=total_dups)
    with col4:
        total_outliers = int(df_history["outliers"].sum()) if not df_history.empty else 0
        st.metric(label="Outliers Flagged", value=total_outliers)
        
    st.write("---")
    
    
    # 3. STATIC TRANSFORMATION LOG TABLE (FR-4.1)
    
    st.subheader("SQLite Database Records")
    if not df_records.empty:
        # st.table creates a 100% static, basic HTML table with NO show/hide column selectors
        st.table(df_records[["document_id", "patient_name", "hospital_name", "reports_date", "ingested_at", "status"]])
    else:
        st.warning("The database is currently empty! Click 'Run Processing Pipeline ' in the sidebar.")
        
    st.write("---")
    
   
    # 4. SIDE-BY-SIDE PATIENT AUDITOR (FR-5.2)
    
    st.subheader(" Patient Auditor")
    if not df_records.empty:
        selected_id = st.selectbox("Select a Document ID to audit:", df_records["document_id"].tolist())
        
        matching_rows = df_records[df_records["document_id"] == selected_id].to_dict("records")
        if matching_rows:
            patient = matching_rows.pop(0)
            
            left_col, right_col = st.columns(2)
            with left_col:
                st.markdown("**Original Raw File**")
                st.json(json.loads(patient.get("raw_payload", "{}")))
                
            with right_col:
                st.markdown("**Clean Database Output**")
                st.write(f"**Patient:** {patient['patient_name']} | **Clinic:** {patient['hospital_name']} | **Date:** {patient['reports_date']}")
                
                # Render clean results dictionary
                visual_dict = {}
                for test_key in ["Hemoglobin", "WBC_Count", "Serum_Creatinine", "Sodium", "Potassium"]:
                    result_val = patient[f"{test_key}_Result"]
                    if result_val is not None:
                        visual_dict[test_key] = {
                            "Standard Value": result_val,
                            "Validation Label": patient[f"{test_key}_Analytics"]
                        }
                    else:
                        visual_dict[test_key] = "Not present in raw file"
                st.write(visual_dict)
    else:
        st.info("Ingest clinical files first to enable the side-by-side Patient Auditor.")

if __name__ == "__main__":
    main()