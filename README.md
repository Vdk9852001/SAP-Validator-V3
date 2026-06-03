# SAP Post-Load Validation Tool
## SAP 4.7 → S/4HANA Public Cloud | Material Master & More

---

## GETTING STARTED

### Step 2 — Extract the zip
Unzip SAP_Validator.zip to any folder, e.g.:
  C:\SAP_Validator\

### Step 3 — Open a terminal in that folder
Windows: Right-click inside the folder → "Open in Terminal"  (or search for "cmd")
Mac/Linux: Open Terminal and cd to the folder

### Step 4 — Install dependencies (one time only)
  pip install -r requirements.txt

### Step 5 — Start the dashboard
  python dashboard/app.py

### Step 6 — Open your browser
  http://localhost:5000

---

## HOW TO VALIDATE YOUR DATA

### Option A — Upload via the dashboard (easiest)
1. Open http://localhost:5000
2. Click "Upload Source" or "Upload Target" (bottom of left sidebar, or on the welcome screen)
3. Select your source CSV/XLSX and target CSV/XLSX
4. The tool detects the pair within 5 seconds and validates automatically

### Option B — Copy files to watched folders
Source files → sap_validator/data/source/
Target files → sap_validator/data/target/

Files are matched by name:
  data/source/MATERIAL.csv  ↔  data/target/MATERIAL.csv
  data/source/VENDOR.csv    ↔  data/target/VENDOR.csv

### Option C — Use your own folder paths (Settings)
1. Click Settings (top right)
2. Enter your source and target folder paths
3. Click Save Paths — the tool rescans automatically

---

## CONFIGURING PASS THRESHOLD (e.g. 90%)

By default every field must match 100% to be PASS.
To allow some variance (e.g. pass fields with 90%+ match):

1. Click Settings → "Pass Threshold" section
2. Drag the slider to 90 (or type 90 directly)
3. Click "Apply Threshold"
4. All tables re-validate immediately with the new threshold
5. The current threshold is shown in the header badge: "Threshold: 90%"

In the results table a new "Threshold" column shows the target (≥ 90%)
alongside the actual match % so you can see at a glance why each field passed or failed.

---

## SELECTING SPECIFIC FIELDS TO VALIDATE

If you only want to validate certain fields (e.g. just Material Description and Price):

1. Click Settings → "Field Selection" section
2. Un-check "Select all" to deselect everything
3. Check only the fields you care about
4. Click "Apply Selection"
5. Only those fields appear in results and Excel reports

Leave all fields checked (default) to validate everything automatically.

---

## FIELD LABELS (English names)

SAP technical field names (MATNR, MAKTX etc.) are automatically translated to
plain English using the built-in dictionary (e.g. MATNR → "Material Number").

To use your own custom names:
1. Download the sample label CSV from Settings → "Custom Field Labels" → "Sample CSV"
2. Edit it — format is:  FIELD_NAME,YOUR_LABEL
   Example:  MATNR,My Material ID
3. Upload it in Settings → "Custom Field Labels" → "Choose label CSV"
4. All tables re-validate and show your labels immediately

---

## EXCEL REPORTS

An Excel report is generated automatically after every validation run.
Each report contains:
  - Summary tab: run info, record counts, all field results with match %, threshold, PASS/FAIL
  - One FAIL tab per failing field: exact rows with source value vs target value highlighted

To download:
  - Click "↓ Excel" button next to each table's results
  - OR click "Reports" in the header to see and download all historical reports

---

## SAMPLE DATA (included)

Two sample table pairs are included so you can see the tool working immediately:
  data/source/MATERIAL.csv  +  data/target/MATERIAL.csv  (3 deliberate mismatches)
  data/source/VENDOR.csv    +  data/target/VENDOR.csv

---

## FOLDER STRUCTURE

  sap_validator/
    core/
      validator.py        Validation engine
      reporter.py         Excel report generator
      field_labels.py     SAP field name dictionary
    dashboard/
      app.py              Flask web server
      templates/
        dashboard.html    Web UI
    data/
      source/             DROP SOURCE FILES HERE
      target/             DROP TARGET FILES HERE
    reports/              Excel reports saved here automatically
    config.json           Your settings (auto-created)
    custom_labels.csv     Your label overrides (after upload)
    requirements.txt
    README.md

---

## REQUIREMENTS

  pandas >= 2.0
  openpyxl >= 3.1
  flask >= 3.0
  Python >= 3.10

---

## TROUBLESHOOTING

Problem: "pip is not recognized"
Fix: Reinstall Python and tick "Add Python to PATH"

Problem: Port 5000 already in use
Fix: python dashboard/app.py --port 5001  (then open http://localhost:5001)

Problem: KeyError on column name
Fix: The tool auto-uppercases all column headers. Ensure both files have
matching SAP field names (MATNR, MAKTX etc.) or configure a join key in Settings.

Problem: Files not being detected
Fix: Check the folder paths in Settings. Files must be CSV or XLSX.
Both source and target must have the same filename stem (e.g. both named MATERIAL.csv).
