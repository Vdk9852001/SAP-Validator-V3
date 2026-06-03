"""
SAP Field Label Dictionary
Built-in friendly English names for SAP technical field names.
"""

SAP_FIELD_LABELS = {
    "MATNR": "Material Number",    "MAKTX": "Material Description",
    "MAKTG": "Material Description (Upper)",
    "MTART": "Material Type",      "MATKL": "Material Group",
    "MEINS": "Base Unit of Measure","MEINH": "Order Unit",
    "BRGEW": "Gross Weight",       "NTGEW": "Net Weight",
    "GEWEI": "Weight Unit",        "VOLUM": "Volume",
    "VOLEH": "Volume Unit",        "BISMT": "Old Material Number",
    "MFRPN": "Manufacturer Part Number",
    "NORMT": "Industry Standard Description",
    "XCHPF": "Batch Management",   "XSERI": "Serial Number Profile",
    "EANNR": "EAN / UPC Number",   "GROES": "Size / Dimensions",
    "WRKST": "Basic Material",     "PRDHA": "Product Hierarchy",
    "SPART": "Division",           "PRCTR": "Profit Centre",
    "MSTAE": "Cross-Plant Material Status",
    "WERKS": "Plant",              "LGORT": "Storage Location",
    "EKGRP": "Purchasing Group",   "DISPO": "MRP Controller",
    "DISMM": "MRP Type",           "MINBE": "Reorder Point",
    "EISBE": "Safety Stock",       "MABST": "Maximum Stock Level",
    "PLIFZ": "Planned Delivery Time (Days)",
    "WEBAZ": "Goods Receipt Processing Time",
    "BESKZ": "Procurement Type",   "SOBSL": "Special Procurement Type",
    "DISLS": "Lot Size",           "BSTMI": "Minimum Lot Size",
    "BSTMA": "Maximum Lot Size",   "BSTFE": "Fixed Lot Size",
    "STPRS": "Standard Price",     "VPRSV": "Price Control",
    "PEINH": "Price Unit",         "WAERS": "Currency",
    "BKLAS": "Valuation Class",    "VERPR": "Moving Average Price",
    "ZKPRS": "Future Planned Price",
    "VKORG": "Sales Organisation", "VTWEG": "Distribution Channel",
    "VRKME": "Sales Unit",         "DWERK": "Delivering Plant",
    "TRAGR": "Transportation Group","LADGR": "Loading Group",
    "MTPOS": "Item Category Group","KONDM": "Material Pricing Group",
    "LIFNR": "Vendor Number",      "NAME1": "Vendor Name",
    "NAME2": "Vendor Name 2",      "STRAS": "Street Address",
    "ORT01": "City",               "PSTLZ": "Postal Code",
    "LAND1": "Country",            "REGIO": "Region / State",
    "SPRAS": "Language",           "TELF1": "Telephone",
    "KTOKK": "Vendor Account Group","AKONT": "Reconciliation Account",
    "ZTERM": "Payment Terms",      "ZWELS": "Payment Methods",
    "STCD1": "Tax Number 1",       "STCD2": "Tax Number 2",
    "BANKS": "Bank Country",       "BANKL": "Bank Key",
    "BANKN": "Bank Account Number",
    "KUNNR": "Customer Number",    "KTOKD": "Customer Account Group",
    "VKBUR": "Sales Office",       "VKGRP": "Sales Group",
    "BZIRK": "Sales District",     "KDGRP": "Customer Group",
    "SAKNR": "GL Account Number",  "BUKRS": "Company Code",
    "TXT20": "GL Short Text",      "TXT50": "GL Long Text",
    "KTOKS": "GL Account Group",   "XBILK": "Balance Sheet Account",
    "FSTAG": "Field Status Group",
    "BELNR": "Document Number",    "GJAHR": "Fiscal Year",
    "BUZEI": "Line Item",          "BLDAT": "Document Date",
    "BUDAT": "Posting Date",       "WRBTR": "Amount (Doc Currency)",
    "DMBTR": "Amount (Local Currency)",
    "SGTXT": "Item Text",          "ZUONR": "Assignment",
    "XBLNR": "Reference Document", "BLART": "Document Type",
    "ZFBDT": "Baseline Payment Date",
    "ZBD1T": "Cash Discount Days 1","ZBD2T": "Cash Discount Days 2",
    "ZBD1P": "Cash Discount % 1",  "ZBD2P": "Cash Discount % 2",
    "ERDAT": "Created On",         "ERNAM": "Created By",
    "LAEDA": "Last Changed Date",  "AENAM": "Last Changed By",
    "LVORM": "Deletion Flag",      "MANDT": "Client",
}


def get_label(field_name: str, custom_map: dict = None) -> str:
    field_upper = field_name.strip().upper()
    if custom_map and field_upper in custom_map:
        return custom_map[field_upper]
    return SAP_FIELD_LABELS.get(field_upper, field_name)


def load_custom_labels(csv_path: str) -> dict:
    import csv
    from pathlib import Path
    custom = {}
    path = Path(csv_path)
    if not path.exists():
        return custom
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue
            key, label = row[0].strip().upper(), row[1].strip()
            if key in ("FIELD", "FIELD_NAME", "SAP_FIELD", "TECHNICAL"):
                continue
            if key and label:
                custom[key] = label
    return custom
