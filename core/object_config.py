"""
SAP Object Configuration
Defines join keys and key fields for each SAP migration object.
Add your own objects at the bottom.
"""

from pathlib import Path

SAP_OBJECT_CONFIG = {

    # ── Material Master ───────────────────────────────────────────────────────
    "MATERIAL": {
        "join_key":    "MATNR",
        "description": "Material Master",
        "key_fields":  ["MATNR", "MAKTX", "MTART", "MATKL", "MEINS",
                        "BRGEW", "NTGEW", "STPRS", "VPRSV", "WERKS"],
    },

    # ── Vendor Master ─────────────────────────────────────────────────────────
    "VENDOR": {
        "join_key":    "LIFNR",
        "description": "Vendor Master",
        "key_fields":  ["LIFNR", "NAME1", "KTOKK", "LAND1", "STRAS",
                        "ORT01", "PSTLZ", "ZTERM", "AKONT", "WAERS"],
    },

    # ── Customer Master ───────────────────────────────────────────────────────
    "CUSTOMER": {
        "join_key":    "KUNNR",
        "description": "Customer Master",
        "key_fields":  ["KUNNR", "NAME1", "KTOKD", "LAND1", "STRAS",
                        "ORT01", "PSTLZ", "ZTERM", "WAERS", "VKORG"],
    },

    # ── GL Accounts ───────────────────────────────────────────────────────────
    "GL_ACCOUNT": {
        "join_key":    "SAKNR",
        "description": "GL Account / Chart of Accounts",
        "key_fields":  ["SAKNR", "BUKRS", "TXT20", "TXT50", "KTOKS",
                        "XBILK", "GVTYP", "FSTAG"],
    },

    # ── Open Items AR ─────────────────────────────────────────────────────────
    "OPEN_ITEMS_AR": {
        "join_key":    "BELNR",
        "description": "Open Items — Accounts Receivable",
        "key_fields":  ["BELNR", "GJAHR", "BUZEI", "KUNNR", "BLDAT",
                        "BUDAT", "WRBTR", "DMBTR", "ZTERM", "ZFBDT"],
    },

    # ── Open Items AP ─────────────────────────────────────────────────────────
    "OPEN_ITEMS_AP": {
        "join_key":    "BELNR",
        "description": "Open Items — Accounts Payable",
        "key_fields":  ["BELNR", "GJAHR", "BUZEI", "LIFNR", "BLDAT",
                        "BUDAT", "WRBTR", "DMBTR", "ZTERM", "ZFBDT"],
    },

    # ── Purchase Orders ───────────────────────────────────────────────────────
    "PURCHASE_ORDER": {
        "join_key":    "EBELN",
        "description": "Purchase Orders",
        "key_fields":  ["EBELN", "EBELP", "LIFNR", "MATNR", "MENGE",
                        "MEINS", "NETPR", "PEINH", "WAERS", "WERKS"],
    },

    # ── Sales Orders ─────────────────────────────────────────────────────────
    "SALES_ORDER": {
        "join_key":    "VBELN",
        "description": "Sales Orders",
        "key_fields":  ["VBELN", "POSNR", "KUNNR", "MATNR", "KWMENG",
                        "VRKME", "NETWR", "WAERS", "WERKS", "VKORG"],
    },

    # ── Asset Master ─────────────────────────────────────────────────────────
    "ASSET": {
        "join_key":    "ANLN1",
        "description": "Fixed Asset Master",
        "key_fields":  ["ANLN1", "ANLN2", "BUKRS", "ANLKL", "TXT50",
                        "AKTIV", "DEAKT", "KOSTL", "AUFNR", "WAERS"],
    },

    # ── Cost Centre ───────────────────────────────────────────────────────────
    "COST_CENTRE": {
        "join_key":    "KOSTL",
        "description": "Cost Centre Master",
        "key_fields":  ["KOSTL", "BUKRS", "KOKRS", "KTEXT", "KOSAR",
                        "ABTEI", "VERAK", "WAERS", "DATAB", "DATBI"],
    },

    # ── Profit Centre ────────────────────────────────────────────────────────
    "PROFIT_CENTRE": {
        "join_key":    "PRCTR",
        "description": "Profit Centre Master",
        "key_fields":  ["PRCTR", "KOKRS", "KTEXT", "LTEXT", "ABTEI",
                        "VERAK", "WAERS", "DATAB", "DATBI"],
    },

    # ── Bank Master ──────────────────────────────────────────────────────────
    "BANK": {
        "join_key":    "BANKL",
        "description": "Bank Master",
        "key_fields":  ["BANKL", "BANKS", "BANKA", "STRAS", "ORT01",
                        "SWIFT", "BGRUP"],
    },

    # ── Inventory / Stock ────────────────────────────────────────────────────
    "INVENTORY": {
        "join_key":    "MATNR",
        "description": "Inventory / Stock Balances",
        "key_fields":  ["MATNR", "WERKS", "LGORT", "LABST", "INSME",
                        "EINME", "SPEME", "MEINS", "STPRS", "WAERS"],
    },
}


def get_object_config(name: str) -> dict:
    """
    Auto-detect SAP object config from a table/file name.
    Tries exact match first, then partial match.

    Examples:
        MATERIAL          -> MATERIAL config
        VENDOR_DATA       -> VENDOR config
        customer_master   -> CUSTOMER config
        OPEN_ITEMS_AR     -> OPEN_ITEMS_AR config
    """
    stem = str(name).upper().replace("-", "_").replace(" ", "_")

    # Direct match
    if stem in SAP_OBJECT_CONFIG:
        return SAP_OBJECT_CONFIG[stem]

    # Partial match — longest key that appears in the stem wins
    matches = [(k, v) for k, v in SAP_OBJECT_CONFIG.items() if k in stem]
    if matches:
        best = sorted(matches, key=lambda x: len(x[0]), reverse=True)[0]
        return best[1]

    return {}
