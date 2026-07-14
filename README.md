# Veritas Medical Data Standardisation Pipeline - Prototype Documentation

This repository contains the functional desktop prototype for the **Veritas Claims Medical Data Standardisation Pipeline**. Designed to resolve severe data-quality challenges at the intersection of healthcare providers and insurance payors, this pipeline ingest unstructured, highly nested, and misspelled JSON medical reports from clinical sources, standardising them into a canonical, relational format for automated adjudication [1, 2].

The prototype is fully compliant with **Functional Requirements (FR-1 to FR-5)** and presents a production-scaling blueprint addressing **Non-Functional Requirements (NFR-1 to NFR-5)** as specified in the Veritas Claims Engineering guidelines [4, 11].


## 1. Business Context & Problem Statement
Every day, Veritas Claims ingests and adjudicates over **200,000 medical reports** submitted by a nationwide network of over **500 clinics, hospitals, and diagnostic labs** [1, 2]. Because these providers operate on completely independent electronic health record (EHR) systems, they transmit data using highly inconsistent conventions [1].

### Downstream Consequences of Messy Data:
*   **Adjudication Failures:** Claims analysts cannot compare lab values across clinics because `'Haemoglobin'`, `'Hemoglobin'`, and `'aemoglobin'` are treated as distinct tests [3].
*   **Rule Engine Crashes:** Automated rule engines crash when evaluating non-numeric or contaminated result fields (e.g., `'13.7 g/dl'` or `'4,290'`) [3, 2].
*   **Financial Leakage:** Extreme physiological outliers slip through undetected, leading to incorrect claim approvals and fraud [3].
*   **Inconsistent Reporting:** Regulatory audits are compromised because patient demographic markers (age, gender, dates) lack a unified schema [3].

This pipeline acts as an automated assembly line that transforms raw hospital payloads into structured, verified database assets—minimizing human review, accelerating adjudication speed, and reducing financial risk [3, 4].

##  2. Setup & Execution Instructions

### Prerequisites
*   **Python 3.12+**
*   **Pandas** and **Streamlit** libraries installed.

### Quick Start Installation
1.  **Extract the project folder** to your Desktop or target directory.
2.  **Open your terminal** (Command Prompt on Windows or Terminal on macOS).
3.  **Navigate to the project directory**:
    ```bash
    cd C:\Users\Admin\Desktop
    ```
4.  **Install the required libraries**:
    ```bash
    pip install pandas streamlit
    ```
5.  **Start the Streamlit application**:
    ```bash
    python -m streamlit run app1.py
    ```
6.  **Access the Portal**: Open your web browser and navigate to `http://localhost:8501`.



##  3. Core Pipeline Architecture (FR-1 to FR-5)

The code inside `app1.py` executes in 5 distinct, sequential stages to process raw inputs:


[Incoming JSON Files] 
       │
       ▼
 1. DATA INGESTION (FR-1) ────────► Deduplication Filter (FR-1.2) [Suppresses Duplicates]
       │
       ▼
 2. STANDARDISATION (FR-2) ───────► Configurable Mapping Lookup (FR-2.1) [Translates names]
       │                            ► Numeric Regex Stripper (FR-2.3) [Extracts decimals]
       │                            ► Unit Scaling Engine (FR-2.4) [Harmonizes units]
       ▼
 3. VALIDATION ENGINE (FR-3) ─────► Reference Range Matcher (FR-3.1) [Validates bounds]
       │                            ► Outlier Identification (FR-3.2) [Flags impossible values]
       ▼
 4. DATABASE LOADER (FR-4) ───────► Writes to transactional SQLite DB in Wide Schema (FR-2.2)
       │
       ▼
 5. OPERATIONAL UI (FR-5) ────────► Interactive Streamlit Dashboard (FR-5.1)
                                    ► Raw vs. Standardised Side-by-Side Inspector (FR-5.2)


### Stage 1: Data Ingestion (FR-1)
*   **Multi-source Discovery (FR-1.1):** The pipeline automatically scans the `sample_data` directory, discovering incoming JSON records dynamically [21].
*   **Duplicate Prevention (FR-1.2):** Before writing, the ingestion engine queries the SQLite index. If a clinic transmits the same patient discharge record twice (e.g., `sample2.json` and `sample3.json`), the duplicate is permanently suppressed, maintaining database integrity [14, 22].
*   **Schema-on-Read Flexibility (FR-1.3):** The ingestion module uses recursive `.get()` structures. It safely parses varied, highly nested JSON files (such as pure discharge summaries or complex multi-page laboratory reports) without throwing crashing errors or requiring schema changes [5, 21].

### Stage 2: Clinical Standardisation (FR-2)
*   **Test Name Normalisation (FR-2.1):** It uses a configurable lookup map (`TEST_NAME_MAP`) to translate variant, misspelled clinic terms (e.g., `'aemoglobin'`, `'tal WBC Count'`, `'sr creatinine'`) into canonical keys [5, 28].
*   **Fixed Column Schema (FR-2.2):** For each of the 5 canonical tests, the pipeline guarantees exactly 5 dedicated database columns: `Test_Name`, `Test_Result`, `Test_Range`, `Test_Unit`, and `Test_Analytics` [6]. If a test is absent from a patient record, these columns remain safely blank (`NULL`) [6].
*   **Numeric Conversion (FR-2.3):** Using Python’s built-in regular expression engine, the pipeline strips textual noise, units, and thousands-separator commas (e.g., converting `'13.7 g/dl'` to `13.7` and `'4,290'` to `4290.0`) [6].
*   **Unit Harmonisation (FR-2.4):** If a lab measures white blood cells in millions (e.g., `'5.45 mil/cu.mm'`), the harmonizer automatically multiplies the value by `1,000` to scale it to the standard canonical measurement of `5450.0 cells/cu.mm` [6].

### Stage 3: Clinical Validation & Analytics (FR-3)
*   **Range Validation (FR-3.1):** The pipeline evaluates clean results against medically accepted boundaries [7]. For example, if Potassium is `6.2 mmol/L` (normal range: `3.5 - 5.1`), it is flagged as `Above Range` [8].
*   **Outlier Detection (FR-3.2):** Extreme or physiologically near-impossible readings—such as a Hemoglobin count of `1.5` or a WBC Count of `120,000`—are flagged as `Outlier` instead of standard out-of-range limits, flagging them for immediate operational audit [8].
*   **Grounded Classification (FR-3.3):** It populates the standard analytics column with one of: `Within Range`, `Above Range`, `Below Range`, `Outlier`, or `N/A` [8].

###  Stage 4: Relational Storage (FR-4)
*   **Structured SQL Load (FR-4.1):** Transformed rows are written transactionally into a local relational database (`veritas_claims.db`) using Python's native `sqlite3` engine [9, 22].
*   **Auditable Lineage (NFR-4.2):** The database records retain crucial metadata—including `trace_id`, `correlation_id`, `ingested_at` timestamp, and the full raw source JSON string—enabling clinical audits at any time [9, 15, 16].

###  Stage 5: Operational UI (FR-5)
*   **Live Dashboard Metrics (FR-5.1):** streamlit presents live metrics at the top of the interface: Total Ingested Records, Executions, Suppressed Duplicates, and Active Outliers [10, 22].
*   **Record Inspector (FR-5.2):** Operations teams can select any processed record by ID to view the original raw JSON payload on the left and the clean standardized columns on the right [10, 22].



## 4. Production Cloud Architecture & Scaling (NFR-1 to NFR-5)

To scale this local prototype to handle the **200,000 daily files** under Veritas Claims' strict SLAs, the pipeline is designed to easily transition to a serverless cloud infrastructure on Google Cloud Platform (GCP) [11, 19]:

[Clinic EHR System] 
       │  (Transmits raw JSON file)
       ▼
┌────────────────────────────────────────────────────────┐
│ 1. INGESTION LAYER                                     │
│    • Google Cloud Storage (GCS) Incoming Bucket        │
│    • Organized dynamically by: clinic_id / date        │
└───────────────────────┬────────────────────────────────┘
                        │  (Event Notification Trigger)
                        ▼
┌────────────────────────────────────────────────────────┐
│ 2. COMPUTE & PROCESSING LAYER                          │
│    • Google Cloud Run (Autoscaling Serverless Container)│
│    • Processes up to 400,000 burst files horizontally │
└───────────────────────┬────────────────────────────────┘
                        │
         ┌──────────────┴──────────────┐  (If Success)
         ▼ (If Corrupted JSON File)    ▼
┌────────────────────────┐   ┌───────────────────────────┐
│ 3A. RECOVERY LAYER     │   │ 3B. STORAGE LAYER         │
│    • Dead-Letter Queue │   │    • BigQuery Analytics   │
│    • Pub/Sub Alerting  │   │    • Raw payload retained │
└────────────────────────┘   └───────────────────────────┘

### Production Non-Functional Blueprints:
1.  **Throughput & Scaling (NFR-1):** In production, our local folder is replaced by a secure **Google Cloud Storage (GCS) Bucket** [18]. The code runs inside **Google Cloud Run** containers, which automatically scale horizontally from 0 to over 100 concurrent instances to handle peak burst volumes of **400,000 files/day** with zero hardware bottlenecks [11, 12, 19].
2.  **Latency SLA (NFR-1.2):** Cloud Run processes records in real-time on arrival (event-driven execution), cutting the ingestion-to-storage database latency down to **less than 12 seconds** (well within the 15-minute SLA limit) [12].
3.  **Zero-Code Onboarding (NFR-2.1):** Clinic mappings, reference limits, and test name standardisations are completely decoupled from the core pipeline logic and stored as independent, editable JSON configuration files [13, 23]. Onboarding a new clinic with unique naming variations requires only a config commit—taking **less than 1 business day** without editing any pipeline code [13].
4.  **Idempotency & Resilience (NFR-3):** System retries are safe. The SQL index enforces a unique constraint on `document_id`, ensuring that if a processing task retries due to network lag, it will update existing rows rather than creating corrupted duplicates [14]. Malformed JSON files are routed to a **Google Pub/Sub Dead-Letter Queue (DLQ)** to prevent downstream pipeline blockages [14, 18].
5.  **Observability & Monitoring (NFR-5):** Containers emit structured JSON logs to **Google Cloud Logging** [16, 17]. Alerts automatically trigger via Cloud Monitoring if processing error rates exceed 1% [16].

## 5. Known Assumptions & Limitations
*   **Local Staging Assumption:** The GCS storage bucket is simulated locally via the `sample_data/` folder [18, 21].
*   **Relational Storage Selection:** We utilize SQLite as a local file-based prototype [22]. For enterprise data lakes, this would scale to **Google BigQuery** or **PostgreSQL** to handle multi-terabyte transactional queries [18].
*   **Exclusion of Qualitative Tests:** The prototype focus is restricted to cleaning and validating numerical laboratory profiles. Complex qualitative tests (such as microscopic comments or pathology tissue reviews) are retained in the database as raw text strings to avoid automated adjudication errors.
