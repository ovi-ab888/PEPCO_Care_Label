# ================================================================
# PART 1 — PAGE CONFIG + IMPORTS + THEME + PASSWORD + CONSTANTS
# ================================================================

# ---------- PAGE CONFIG (must be at top) ----------
import streamlit as st
st.set_page_config(
    page_title="PEPCO",
    page_icon="🧾",
    layout="wide"
)

# ---------- Imports ----------
import fitz  # PyMuPDF
import pandas as pd
import re
from io import StringIO
import csv as pycsv
from datetime import datetime, timedelta
import os
import requests


# ================================================================
#  LOGO & THEME
# ================================================================
LOGO_PNG = "logo.png"
LOGO_SVG = "logo.svg"

THEME_CSS = """
<style>
:root{
  --card-bg: rgba(255,255,255,.04);
  --card-br: rgba(255,255,255,.12);
  --input-bg: rgba(255,255,255,.08);
  --input-br: rgba(255,255,255,.25);
  --txt:      #E9ECF6;
  --muted:    #C2C8DF;
}

.block-container{max-width:1120px; padding-top:1rem; padding-bottom:3rem;}

h1,h2,h3{font-weight:700;}
h1{letter-spacing:.2px;} h2,h3{letter-spacing:.1px;}

section[data-testid="stFileUploader"],
div[data-testid="stDataFrameContainer"],
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stDataEditor"]){
  background:var(--card-bg)!important;
  border:1px solid var(--card-br)!important;
  border-radius:14px!important;
  padding:12px 14px;
  box-shadow:0 1px 8px rgba(0,0,0,.12);
}

label, .stMultiSelect label, .stSelectbox label, .stNumberInput label, .stTextInput label{
  color:var(--txt)!important; font-weight:500;
}

input, textarea{
  color:var(--txt)!important;
  background:var(--input-bg)!important;
  border-color:var(--input-br)!important;
}
input::placeholder, textarea::placeholder{
  color:var(--muted)!important; opacity:.95;
}

div[data-baseweb="select"] > div{
  background:var(--input-bg)!important;
  border-color:var(--input-br)!important;
  border-radius:12px!important;
}
div[data-baseweb="select"] input{ color:var(--txt)!important; }
div[data-baseweb="select"] svg{ opacity:.9; }

div[data-testid="stNumberInput"] input{
  color:var(--txt)!important;
  background:var(--input-bg)!important;
  border-color:var(--input-br)!important;
}

.stButton > button{
  border-radius:12px; padding:.55rem 1rem;
}

[data-testid="stTable"] td,[data-testid="stTable"] th{
  padding:.45rem .6rem;
}
</style>
"""


# ================================================================
#  PASSWORD CHECK SYSTEM
# ================================================================
def check_password():
    """Simple password gate using secrets or environment."""
    expected = None

    try:
        expected = st.secrets.get("app_password", None)
    except Exception:
        expected = None

    if expected is None:
        expected = os.environ.get("PEPCO_APP_PASSWORD")

    if expected is None:
        st.error("App password not configured. Please set 'app_password' in secrets or PEPCO_APP_PASSWORD env var.")
        return False

    def _password_entered():
        if st.session_state.get("password") == expected:
            st.session_state["password_correct"] = True
            try:
                del st.session_state["password"]
            except Exception:
                pass
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", None) is True:
        return True

    st.text_input("Enter Your Access Code", type="password", key="password", on_change=_password_entered)

    if st.session_state.get("password_correct") is False:
        st.error("Your password Incorrect, Please contact Mr. Ovi")

    return False


# ================================================================
#  CONSTANTS & MAPPINGS
# ================================================================
WASHING_CODES = {
    '1': '১২৩৪৫', '2': '১৪৭৮৫', '3': 'djnst', '4': 'djnpt', '5': 'djnqt',
    '6': 'djnqt', '7': 'gjnpt', '8': 'gjnpu', '9': 'gjnqt', '10': 'gjnqu',
    '11': 'ijnst', '12': 'ijnsu', '13': 'ijnpu', '14': 'ijnsv', '15': 'djnsw'
}

COLLECTION_MAPPING = {
    "a": {"CUTE BEAR": "MODERN 1", "SUMMER CHERRY": "ROMANTIC 1", "AUTUMN": "ROMANTIC 2"},
    "d_girls": {"FLOWER MOUSE": "MODERN 1", "LITTEL FOREST": "ROMANTIC 1"},
    "b": {"DOGS&FRIENDS": "MODERN 1", "EXPOLORE THE MOUNTINE": "MODERN 2", "SUMMER FUN": "MODERN 4", "COOL TRIP": "CLASSIC 1", "COLLEGE BEARS": "CLASSIC 1"},
    "d": {"DOGS FRIENDS": "CLASSIC 1", "FOREST STORY": "MODERN 1", "LITTLE DREAMER": "MODERN 1", "X-MAS": "CLASSIC 2"},
    "yg": {"PONNY_RAINBOW": "COLLECTION 1", "MEOW_STORY": "COLLECTION 2", "BTS": "COLLECTION 3", "COZY AUTUMN": "COLLECTION 4", "WINTER BALLET": "COLLECTION 5", "XMAS": "COLLECTION 6", "PARTY": "COLLECTION 7"},
    "og": {"TRANSITIONAL_GRAFFITI VIBES": "COLLECTION_0", "COOL STYLE": "COLLECTION_1", "COOL COLLEGE LEAGUE": "COLLECTION_2", "GLAMROCK GIRL": "COLLECTION_3", "COZYTIME": "COLLECTION_4", "XMAS & PARTY": "COLLECTION_5"},
    "yb": {"XXXXX_1": "COLLECTION_1", "XXXXX_2": "COLLECTION_2", "XXXXX_3": "COLLECTION_3", "XXXXX_4": "COLLECTION_4", "XXXXX_5": "COLLECTION_5"},
    "ob": {"STREET RACING": "COLLECTION_1", "CAMPUS LIFE": "COLLECTION_2", "DIGITAL RIDE": "COLLECTION_3", "XMAS": "COLLECTION_4"},
    "l": {"XXXXX_1": "COLLECTION_1", "XXXXX_2": "COLLECTION_2", "XXXXX_3": "COLLECTION_3", "XXXXX_4": "COLLECTION_4", "XXXXX_5": "COLLECTION_5"},
    "m": {"XXXXX_1": "COLLECTION_1", "XXXXX_2": "COLLECTION_2", "XXXXX_3": "COLLECTION_3", "XXXXX_4": "COLLECTION_4", "XXXXX_5": "COLLECTION_5"},
}


# ================================================================
# PART 2 — DATA LOADERS + HELPER FUNCTIONS
# ================================================================

# ================================================================
#  CARE LABEL & COMPOSITION LOADER (4 sheets from Google Sheet)
# ================================================================
@st.cache_data(ttl=600)
def load_care_composition_data():
    """Load 4 sheets/tables from Google Sheet"""
    
    BASE_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQtV5x4B3Sf_CCIMLCfvPtSP8nYru5BMAh5Xe4wWkqcrzZqT2cRJ7JYlvaHrsXql0h9Dnqohvq2mrKM/pub"
    
    sheets_config = {
        "comp_instructions": {"url": f"{BASE_URL}?gid=0&single=true&output=csv", "name": "Composition Instructions"},
        "materials": {"url": f"{BASE_URL}?gid=1935147264&single=true&output=csv", "name": "Materials"},
        "care_instructions": {"url": f"{BASE_URL}?gid=21483732&single=true&output=csv", "name": "Care Instructions"},
        "component_names": {"url": f"{BASE_URL}?gid=0&single=true&output=csv", "name": "Component Names"}
    }
    
    result = {}
    for key, config in sheets_config.items():
        try:
            df = pd.read_csv(config["url"])
            if not df.empty:
                result[key] = df
            else:
                result[key] = pd.DataFrame()
        except Exception:
            result[key] = pd.DataFrame()
    
    return result


# ================================================================
#  COMPONENT NAMES TRANSLATIONS LOADER
# ================================================================
@st.cache_data(ttl=600)
def load_component_translations():
    """Load component name translations from Google Sheet"""
    care_data = load_care_composition_data()
    
    if not care_data["component_names"].empty:
        return care_data["component_names"]
    else:
        return pd.DataFrame({
            "EN": ["Main fabric", "Lining", "Pocket bag", "Trim", "Hood", "Collar", "Cuff"],
            "AL": ["Pëlhurë kryesore", "Llastik", "Thes me xhepa", "Shkurtim", "Kapuç", "Jakë", "Manshetë"],
            "BG": ["Основен плат", "Подплата", "Вътрешен джоб", "Подстригване", "Качулка", "Яка", "Маншет"]
        })


# ================================================================
#  PRICE DATA LOADER (Google Sheet)
# ================================================================
@st.cache_data(ttl=600)
def load_price_data():
    """Load currency price ladder from Google Sheet."""
    try:
        url = ("https://docs.google.com/spreadsheets/d/e/"
               "2PACX-1vRdAQmBHwDEWCgmLdEdJc0HsFYpPSyERPHLwmr2tnTYU1BDWdBD6I0ZYfEDzataX0wTNhfLfnm-Te6w/"
               "pub?gid=583402611&single=true&output=csv")
        df = pd.read_csv(url)
        if df.empty:
            st.error("Price data sheet is empty")
            return None
        price_data = {}
        for currency in df.columns:
            price_data[currency] = df[currency].dropna().tolist()
        return price_data
    except Exception as e:
        st.error(f"Failed to load price data: {str(e)}")
        return None


# ================================================================
#  PRODUCT TRANSLATION LOADER
# ================================================================
@st.cache_data(ttl=600)
def load_product_translations():
    """Load product name translations from Google Sheet."""
    try:
        sheet_id = "1ue68TSJQQedKa7sVBB4syOc0OXJNaLS7p9vSnV52mKA"
        sheet_name = "SS26 Product_Name"
        encoded = requests.utils.quote(sheet_name)
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={encoded}"
        df = pd.read_csv(url)
        if df.empty:
            st.error("Loaded translations but sheet appears empty")
        return df
    except Exception as e:
        st.error(f"Failed to load translations: {str(e)}")
        return pd.DataFrame()


# ================================================================
#  MATERIAL TRANSLATION LOADER
# ================================================================
@st.cache_data(ttl=600)
def load_material_translations():
    """Load material translations (AL, MK) with fallback."""
    try:
        url = ("https://docs.google.com/spreadsheets/d/e/"
               "2PACX-1vRdAQmBHwDEWCgmLdEdJc0HsFYpPSyERPHLwmr2tnTYU1BDWdBD6I0ZYfEDzataX0wTNhfLfnm-Te6w/"
               "pub?gid=1096440227&single=true&output=csv")
        df = pd.read_csv(url)
        if df.empty:
            raise ValueError("Empty sheet")
        material_translations = []
        for _, row in df.iterrows():
            name = None
            if 'Name' in row and pd.notna(row['Name']):
                name = row['Name']
            else:
                try:
                    name = row.iloc[0]
                except Exception:
                    name = None
            if not name or pd.isna(name):
                continue
            for lang in ['AL', 'MK']:
                tr = row.get(lang, "")
                tr = "" if pd.isna(tr) else tr
                material_translations.append({'material': name, 'language': lang, 'translation': tr})
        if not material_translations:
            raise ValueError("No material rows produced")
        return pd.DataFrame(material_translations)
    except Exception as e:
        st.warning(f"Could not load material translations ({e}). Using fallback.")
        fallback = [{'material': 'Cotton', 'language': 'AL', 'translation': 'Pambuk'},
                    {'material': 'Cotton', 'language': 'MK', 'translation': 'Памук'},
                    {'material': 'Polyester', 'language': 'AL', 'translation': 'Poliester'},
                    {'material': 'Polyester', 'language': 'MK', 'translation': 'Полиестер'},
                    {'material': 'Elastane', 'language': 'AL', 'translation': 'Elastan'},
                    {'material': 'Elastane', 'language': 'MK', 'translation': 'Еластан'}]
        return pd.DataFrame(fallback)


# ================================================================
#  HELPER FUNCTIONS
# ================================================================

def format_number(value, currency):
    """Format numeric pricing based on currency."""
    try:
        if isinstance(value, str):
            value = float(value.replace(',', '.'))
        if currency in ['EUR', 'BGN', 'BAM', 'RON', 'PLN']:
            formatted = f"{float(value):,.2f}".replace(".", ",")
            if ',' in formatted:
                parts = formatted.split(',')
                parts[0] = parts[0].replace('.', '')
                formatted = ','.join(parts)
            return formatted
        return str(int(float(value)))
    except (ValueError, TypeError):
        return str(value)


def find_closest_price(pln_value):
    """Returns matching row of other currencies for the PLN price."""
    try:
        price_data = load_price_data()
        if not price_data or 'PLN' not in price_data:
            st.error("Price data not available")
            return None
        pln_value = float(pln_value)
        ladder = price_data['PLN']
        if pln_value not in ladder:
            st.error(f"PLN {pln_value} not found in price sheet.")
            return None
        idx = ladder.index(pln_value)
        return {currency: format_number(values[idx], currency)
                for currency, values in price_data.items() if currency != 'PLN'}
    except Exception as e:
        st.error(f"Invalid price value: {str(e)}")
        return None


def get_classification_type(item_class):
    if not item_class:
        return None
    ic = item_class.lower()
    if 'younger girls outerwear' in ic:
        return 'yg'
    if 'older girls outerwear' in ic:
        return 'og'
    if 'younger boys outerwear' in ic:
        return 'yb'
    if 'older boys outerwear' in ic:
        return 'ob'
    if 'baby girls outerwear' in ic:
        return 'a'
    if 'baby boys outerwear' in ic:
        return 'b'
    if 'baby girls essentials' in ic:
        return 'd_girls'
    if 'baby boys essentials' in ic:
        return 'd'
    if 'ladies outerwear' in ic:
        return 'l'
    if 'mens outerwear' in ic:
        return 'm'
    return None


def map_item_class_to_dept_label(item_class):
    if not item_class:
        return None
    ic = item_class.lower()
    if 'baby boys outerwear' in ic or 'baby boys essentials' in ic:
        return "Baby Boy"
    if 'baby girls outerwear' in ic or 'baby girls essentials' in ic:
        return "Baby Girl"
    if 'younger boys outerwear' in ic or 'older boys outerwear' in ic:
        return "Boys"
    if 'younger girls outerwear' in ic or 'older girls outerwear' in ic:
        return "Girls"
    if 'ladies outerwear' in ic:
        return "Women"
    if 'mens outerwear' in ic:
        return "Mens"
    return None


def get_dept_value(item_class):
    if not item_class:
        return ""
    ic = item_class.lower()
    if any(x in ic for x in ['baby boys', 'baby girls']):
        return "BABY"
    if any(x in ic for x in ['younger boys', 'younger girls']):
        return "KIDS"
    if any(x in ic for x in ['older girls', 'older boys']):
        return "TEENS"
    if 'ladies outerwear' in ic:
        return "WOMEN"
    if 'mens outerwear' in ic:
        return "MEN"
    return ""


def modify_collection(collection, item_class):
    if not item_class:
        return collection
    ic = item_class.lower()
    if any(x in ic for x in ['younger boys', 'older boys']):
        return f"{collection} B"
    if any(x in ic for x in ['younger girls', 'older girls']):
        return f"{collection} G"
    return collection


def clean_item_name_english(name: str) -> str:
    if not isinstance(name, str):
        return ""
    text = name.strip()
    lower = text.lower()
    prefixes = ["xxxxx", "xxxxx", "xxxxx", "xxxxx", "xxxxx", "xxxxx", "xxxxx", "xxxxx"]
    for p in prefixes:
        if lower.startswith(p):
            cut_len = len(p)
            text = text[cut_len:].strip(" -_,./").strip()
            break
    return text.upper()


# ================================================================
# PART 3 — PDF EXTRACTION
# ================================================================

def extract_colour_from_pdf_pages(pages_text):
    for txt in pages_text:
        m = re.search(r"Colour.*?\n.*?\n\s*([A-Za-z ]+)\s+[0-9]{2}-[0-9]{4}", txt, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip().upper()
    for txt in pages_text:
        m2 = re.search(r"Purchase price.*?\n\s*([A-Za-z ]+)\s+[0-9]{2}-[0-9]{4}", txt, re.IGNORECASE | re.DOTALL)
        if m2:
            return m2.group(1).strip().upper()
    for txt in pages_text:
        if "colour" in txt.lower():
            for line in txt.splitlines():
                if re.search(r"[A-Za-z ]+\s+[0-9]{2}-[0-9]{4}", line):
                    name = line.split()[0:-1]
                    if name:
                        return " ".join(name).upper()
    st.warning("Colour not found in PDF. Enter colour manually:")
    manual = st.text_input("Colour (e.g. WHITE):", key="manual_colour_fix")
    return manual.strip().upper() if manual else "UNKNOWN"


def extract_order_id_only(file):
    pos = None
    try:
        pos = file.tell()
    except Exception:
        pass
    try:
        file.seek(0)
    except Exception:
        pass
    try:
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            page1_text = doc[0].get_text() if len(doc) > 0 else ""
    except Exception:
        try:
            file.seek(0 if pos is None else pos)
        except Exception:
            pass
        return None
    try:
        file.seek(0 if pos is None else pos)
    except Exception:
        pass
    m = re.search(r"Order\s*-\s*ID\s*\.{2,}\s*([A-Z0-9_+-]+)", page1_text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def extract_data_from_pdf(file):
    try:
        raw = file.read()
        if not raw:
            st.error("Empty PDF uploaded.")
            return None
        doc = fitz.open(stream=raw, filetype="pdf")
        if len(doc) < 1:
            st.error("PDF must have at least 1 page.")
            return None
        pages_text = [doc[i].get_text() for i in range(len(doc))]
        full_text = "\n".join(pages_text)
        page1 = pages_text[0]

        m_item = re.search(r"Item\s*name\s*English\s*[:\.]{1,}\s*(.+)", full_text, re.IGNORECASE)
        if not m_item:
            m_item = re.search(r"Item\s*name\s*[:\.]{1,}\s*(.+?)\n", full_text, re.IGNORECASE)
        item_name_en = m_item.group(1).strip() if m_item else None

        merch_code = re.search(r"Merch\s*code\s*\.{2,}\s*([\w/]+)", page1)
        season = re.search(r"Season\s*\.{2,}\s*(\w+)?\s*(\d{2})", page1)
        style_code = re.search(r"\b\d{6}\b", page1)

        style_suffix = ""
        if merch_code and season:
            style_suffix = f"{merch_code.group(1).strip()}{season.group(2)}"
        elif merch_code:
            style_suffix = merch_code.group(1).strip()

        collection = re.search(r"Collection\s*\.{2,}\s*(.+)", page1)
        date_match = re.search(r"Handover\s*date\s*\.{2,}\s*(\d{2}/\d{2}/\d{4})", page1)

        batch = "UNKNOWN"
        if date_match:
            try:
                batch_date = datetime.strptime(date_match.group(1), "%d/%m/%Y")
                batch = (batch_date - timedelta(days=20)).strftime("%m%Y")
            except Exception:
                pass

        order_id = re.search(r"Order\s*-\s*ID\s*\.{2,}\s*(.+)", page1)
        item_class = re.search(r"Item classification\s*\.{2,}\s*(.+)", page1)
        supplier_code = re.search(r"Supplier product code\s*\.{2,}\s*(.+)", page1)
        supplier_name = re.search(r"Supplier name\s*\.{2,}\s*(.+)", page1)

        item_class_value = item_class.group(1).strip() if item_class else "UNKNOWN"
        class_type = get_classification_type(item_class_value)

        collection_value = collection.group(1).split("-")[0].strip() if collection else "UNKNOWN"
        if class_type and class_type in COLLECTION_MAPPING:
            for orig, new in COLLECTION_MAPPING[class_type].items():
                if orig.upper() in collection_value.upper():
                    collection_value = new
                    break

        colour = extract_colour_from_pdf_pages(pages_text)

        skus = []
        barcodes = []
        excluded = set()
        for txt in pages_text:
            skus.extend(re.findall(r"\b\d{8}\b", txt))
            barcodes.extend(re.findall(r"\b\d{13}\b", txt))
            excluded.update(re.findall(r"barcode:\s*(\d{13})", txt))

        def _dedupe(seq):
            seen = set()
            out = []
            for x in seq:
                if x not in seen:
                    seen.add(x)
                    out.append(x)
            return out

        skus = _dedupe(skus)
        barcodes = _dedupe(barcodes)
        valid_barcodes = [b for b in barcodes if b not in excluded]

        if not skus or not valid_barcodes:
            st.error("SKU or Barcode missing.")
            return None

        if len(skus) != len(valid_barcodes):
            min_len = min(len(skus), len(valid_barcodes))
            st.warning(f"SKU ({len(skus)}) and Barcode ({len(valid_barcodes)}) differ. Using first {min_len}.")
            skus = skus[:min_len]
            valid_barcodes = valid_barcodes[:min_len]

        season_value = f"{season.group(1)}{season.group(2)}" if season else "UNKNOWN"

        results = []
        for sku, barcode in zip(skus, valid_barcodes):
            results.append({
                "Order_ID": order_id.group(1).strip() if order_id else "UNKNOWN",
                "Style": style_code.group() if style_code else "UNKNOWN",
                "Colour": colour,
                "Supplier_product_code": supplier_code.group(1).strip() if supplier_code else "UNKNOWN",
                "Item_classification": item_class_value,
                "Supplier_name": supplier_name.group(1).strip() if supplier_name else "UNKNOWN",
                "today_date": datetime.today().strftime('%d-%m-%Y'),
                "Collection": collection_value,
                "Colour_SKU": f"{colour} • SKU {sku}",
                "Style_Merch_Season": f"STYLE {style_code.group()} • {style_suffix} • Batch No./" if style_code else "STYLE UNKNOWN",
                "Batch": f"виготовлення: {batch}",
                "barcode": barcode,
                "Item_name_EN": item_name_en or "",
                "Season": season_value
            })
        return results
    except Exception as e:
        st.error(f"PDF error: {str(e)}")
        return None


# ================================================================
# PART 4 — MAIN PROCESSOR
# ================================================================

def process_pepco_pdf(uploaded_pdf, extra_order_ids: str | None = None):
    """Main pipeline: parse PDF, build DF, apply UI choices, export CSV."""
    
    translations_df = load_product_translations()
    material_translations_df = load_material_translations()
    care_data = load_care_composition_data()
    comp_translations_df = load_component_translations()

    if not (uploaded_pdf and not translations_df.empty):
        return

    result_data = extract_data_from_pdf(uploaded_pdf)
    if not result_data:
        return

    df = pd.DataFrame(result_data)
    first_row = result_data[0] if len(result_data) > 0 else {}
    pdf_item_class = first_row.get("Item_classification", "")
    pdf_item_name_en = (first_row.get("Item_name_EN") or "").strip()

    if extra_order_ids:
        try:
            df['Order_ID'] = df['Order_ID'].astype(str) + "+" + extra_order_ids
        except Exception:
            pass

    # ============================================================
    # UI Controls (Department, Product, Washing, PLN)
    # ============================================================
    c1, c2, c3, c4 = st.columns(4)

    depts = translations_df['DEPARTMENT'].dropna().unique().tolist()
    default_dept_label = map_item_class_to_dept_label(pdf_item_class)
    default_dept_index = 0
    if default_dept_label:
        for i, d in enumerate(depts):
            if str(d).strip().lower() == str(default_dept_label).strip().lower():
                default_dept_index = i
                break

    with c1:
        selected_dept = st.selectbox("Select Department", options=depts, index=default_dept_index, key="ui_dept")

    filtered = translations_df[translations_df['DEPARTMENT'] == selected_dept]
    products = filtered['PRODUCT_NAME'].dropna().unique().tolist()
    default_product_index = 0
    if pdf_item_name_en:
        for i, p in enumerate(products):
            if str(p).strip().lower() == pdf_item_name_en.strip().lower():
                default_product_index = i
                break

    with c2:
        product_type = st.selectbox("Select Product Type", options=products, index=default_product_index, key="ui_product")

    washing_options = list(WASHING_CODES.keys())
    washing_default_index = washing_options.index('9') if '9' in washing_options else 0
    with c3:
        washing_code_key = st.selectbox("Select Washing Code", options=washing_options, index=washing_default_index, key="ui_wash")

    with c4:
        pln_price_raw = st.text_input("Enter PLN Price", key="ui_pln_price")

    pln_price = None
    if pln_price_raw.strip():
        try:
            pln_price = float(pln_price_raw.replace(",", "."))
            if pln_price < 0:
                st.error("Price can't be negative.")
                pln_price = None
        except ValueError:
            st.error("Please enter a valid number like 12.50 or 12,50")
            pln_price = None

    # ============================================================
    # MATERIAL COMPOSITION UI (Clean Simple + Advanced Version)
    # ============================================================
    st.markdown("### 🧵 Material Composition (%)")
    
    materials_df = care_data.get("materials", pd.DataFrame())
    comp_instructions_df = care_data.get("comp_instructions", pd.DataFrame())
    
    # ------------------------------------------------------------
    # Helper Functions for Translations
    # ------------------------------------------------------------
    def get_material_all_languages(mat_name, pct):
        """Get material with percentage in all languages"""
        if materials_df.empty or not mat_name:
            return f"{pct}% {mat_name}"
        
        en_col = materials_df.columns[0]
        row = materials_df[materials_df[en_col].astype(str).str.strip() == mat_name]
        if row.empty:
            return f"{pct}% {mat_name}"
        
        translations = [mat_name]
        for col in materials_df.columns:
            val = row.iloc[0].get(col, "")
            if pd.notna(val) and str(val).strip() and val != mat_name:
                translations.append(str(val).strip())
        
        return f"{pct}% {' / '.join(translations)}"
    
    def get_component_name_translations(comp_name):
        """Get component name in all available languages"""
        if comp_translations_df.empty:
            return comp_name
        
        row = comp_translations_df[comp_translations_df['EN'].astype(str).str.strip() == comp_name]
        if row.empty:
            return comp_name
        
        translations = [comp_name]
        for col in comp_translations_df.columns:
            if col != 'EN':
                val = row.iloc[0].get(col, "")
                if pd.notna(val) and str(val).strip():
                    translations.append(str(val).strip())
        
        return " / ".join(translations)
    
    def get_instruction_all_languages(inst_text):
        """Get composition instruction in all languages"""
        if not inst_text or comp_instructions_df.empty:
            return ""
        
        en_col = comp_instructions_df.columns[0]
        row = comp_instructions_df[comp_instructions_df[en_col].astype(str).str.strip() == inst_text]
        if row.empty:
            return ""
        
        translations = []
        for col in comp_instructions_df.columns:
            val = row.iloc[0].get(col, "")
            if pd.notna(val) and str(val).strip():
                translations.append(str(val).strip())
        
        return " / ".join(translations)
    
    def get_care_instruction_all_languages(inst_text, care_instructions_df):
        """Get care instruction in all languages"""
        if not inst_text or care_instructions_df.empty:
            return ""
        
        en_col = care_instructions_df.columns[0]
        row = care_instructions_df[care_instructions_df[en_col].astype(str).str.strip() == inst_text]
        if row.empty:
            return ""
        
        translations = []
        for col in care_instructions_df.columns:
            val = row.iloc[0].get(col, "")
            if pd.notna(val) and str(val).strip():
                translations.append(str(val).strip())
        
        return " / ".join(translations)
    
    # ------------------------------------------------------------
    # Material Options
    # ------------------------------------------------------------
    materials_options = []
    if not materials_df.empty:
        en_col = materials_df.columns[0]
        materials_options = materials_df[en_col].dropna().astype(str).tolist()
    if not materials_options:
        materials_options = ["Cotton", "Polyester", "Elastane", "Nylon", "Viscose", "Wool"]
    
    # ------------------------------------------------------------
    # Composition Instructions Options
    # ------------------------------------------------------------
    comp_inst_options = [""]
    if not comp_instructions_df.empty:
        en_col = comp_instructions_df.columns[0]
        comp_inst_options.extend(comp_instructions_df[en_col].dropna().astype(str).tolist())
    
    # ------------------------------------------------------------
    # Component Options
    # ------------------------------------------------------------
    component_options = []
    if not comp_translations_df.empty:
        component_options = comp_translations_df["EN"].dropna().astype(str).tolist()
    if not component_options:
        component_options = ["Main fabric", "Outer fabric", "Lining", "Pocket bag", "Collar", "Cuff"]
    
    # ------------------------------------------------------------
    # Mode Toggle
    # ------------------------------------------------------------
    use_advanced_mode = st.toggle("🔧 Advanced Mode (Multiple Components)", value=False)
    
    # ------------------------------------------------------------
    # Session State
    # ------------------------------------------------------------
    if "composition_blocks" not in st.session_state:
        st.session_state.composition_blocks = []
    
    if not st.session_state.composition_blocks:
        st.session_state.composition_blocks.append({
            "component_name": "Main fabric",
            "comp_inst": "",
            "materials": [{"mat": "", "pct": 0}]
        })
    
    def build_material_line(materials, use_translation=True):
        parts = []
        for m in materials:
            if m["mat"] and m["pct"] > 0:
                if use_translation:
                    mat_text = get_material_all_languages(m["mat"], m["pct"])
                else:
                    mat_text = f"{m['pct']}% {m['mat']}"
                parts.append(mat_text)
        return "\n\n".join(parts)
    
    # Output variables
    final_composition_text = ""
    selected_materials = []
    cotton_value = ""
    components_data = []
    material_compositions = {}
    simple_comp_inst = ""
    
    # Render blocks
    for block_idx, block in enumerate(st.session_state.composition_blocks):
        
        with st.container(border=True):
            
            top1, top2 = st.columns([5, 1])
            
            with top1:
                if use_advanced_mode:
                    current_name = block.get("component_name", "Main fabric")
                    name_index = component_options.index(current_name) if current_name in component_options else 0
                    block["component_name"] = st.selectbox(
                        f"Component Name #{block_idx + 1}",
                        options=component_options,
                        index=name_index,
                        key=f"comp_name_{block_idx}"
                    )
                else:
                    st.markdown("#### Simple Composition")
            
            with top2:
                if len(st.session_state.composition_blocks) > 1:
                    st.write("")
                    st.write("")
                    if st.button("🗑️", key=f"remove_block_{block_idx}"):
                        st.session_state.composition_blocks.pop(block_idx)
                        st.rerun()
            
            if use_advanced_mode:
                inst_idx = comp_inst_options.index(block.get("comp_inst", "")) if block.get("comp_inst", "") in comp_inst_options else 0
                block["comp_inst"] = st.selectbox(
                    "Composition Instructions (Optional)",
                    options=comp_inst_options,
                    index=inst_idx,
                    key=f"comp_inst_{block_idx}"
                )
            
            st.markdown("#### Materials")
            
            for mat_idx, mat in enumerate(block["materials"]):
                c1, c2, c3 = st.columns([3, 1.5, 0.7])
                
                with c1:
                    mat_options = [""] + materials_options
                    mat_index = mat_options.index(mat["mat"]) if mat["mat"] in mat_options else 0
                    mat["mat"] = st.selectbox(
                        "Material",
                        options=mat_options,
                        index=mat_index,
                        key=f"mat_{block_idx}_{mat_idx}"
                    )
                
                with c2:
                    mat["pct"] = st.number_input(
                        "%",
                        min_value=0,
                        max_value=100,
                        step=1,
                        value=int(mat["pct"]),
                        key=f"pct_{block_idx}_{mat_idx}"
                    )
                
                with c3:
                    st.write("")
                    if len(block["materials"]) > 1:
                        if st.button("❌", key=f"remove_mat_{block_idx}_{mat_idx}"):
                            block["materials"].pop(mat_idx)
                            st.rerun()
            
            if st.button("➕ Add Material", key=f"add_material_{block_idx}"):
                block["materials"].append({"mat": "", "pct": 0})
                st.rerun()
            
            valid_materials = [m for m in block["materials"] if m["mat"] and m["pct"] > 0]
            total_pct = sum(m["pct"] for m in valid_materials)
            
            if total_pct == 100:
                st.success(f"✅ Total = {total_pct}%")
            elif total_pct < 100 and total_pct > 0:
                st.warning(f"⚠️ Remaining = {100 - total_pct}%")
            elif total_pct > 100:
                st.error(f"❌ Exceeded by {total_pct - 100}%")
            else:
                st.info("📌 Enter material composition")
            
            if valid_materials and total_pct == 100:
                preview_text = build_material_line(valid_materials, use_translation=True)
                
                if use_advanced_mode:
                    comp_translated = get_component_name_translations(block["component_name"])
                    full_preview = f"{comp_translated}: {preview_text}"
                else:
                    full_preview = preview_text
                
                st.code(full_preview, language="text")
            
            if valid_materials and total_pct == 100:
                st.write(f"Debug - Adding component: {block['component_name']} with {len(valid_materials)} materials")  # ডিবাগ
                components_data.append({
                    "name": block["component_name"],
                    "comp_inst": block.get("comp_inst", "") if use_advanced_mode else "",
                    "materials": valid_materials.copy()
                })
                
                for m in valid_materials:
                    if m["mat"] not in selected_materials:
                        selected_materials.append(m["mat"])
    
    if use_advanced_mode:
        if len(st.session_state.composition_blocks) < 5:
            if st.button("➕ Add Component", key="add_component_btn"):
                st.session_state.composition_blocks.append({
                    "component_name": "Main fabric",
                    "comp_inst": "",
                    "materials": [{"mat": "", "pct": 0}]
                })
                st.rerun()
        else:
            st.info("Maximum 5 components allowed")
    
    if not use_advanced_mode:
        simple_comp_inst = st.selectbox(
            "Composition Instructions (Optional)",
            options=comp_inst_options,
            key="simple_comp_inst_global"
        )
    
    # Build final composition text
    composition_lines = []
    
    for comp in components_data:
        material_text = build_material_line(comp["materials"], use_translation=True)
        
        if use_advanced_mode:
            comp_translated = get_component_name_translations(comp["name"])
            # এখানে পরিবর্তন: ":" এর পর "\n\n" যোগ করুন
            line = f"{comp_translated}:\n\n{material_text}"
            
            if comp.get("comp_inst"):
                inst_text = get_instruction_all_languages(comp["comp_inst"])
                if inst_text:
                    line += f"\n\n(Composition Instructions: {inst_text})"
        else:
            line = material_text
            if simple_comp_inst:
                inst_text = get_instruction_all_languages(simple_comp_inst)
                if inst_text:
                    line += f"\n\n(Composition Instructions: {inst_text})"
        
        composition_lines.append(line)
    
    # কম্পোনেন্টগুলোর মধ্যে ২ লাইন গ্যাপ
    final_composition_text = "\n\n".join(composition_lines)
    
    # Build material compositions for AL/MK
    if selected_materials and not material_translations_df.empty:
        for lang in ['AL', 'MK']:
            comp_parts = []
            for comp in components_data:
                for mat in comp["materials"]:
                    t = material_translations_df[
                        (material_translations_df['material'] == mat['mat']) & 
                        (material_translations_df['language'] == lang)
                    ]
                    if not t.empty:
                        comp_parts.append(f"{mat['pct']}% {t['translation'].iloc[0]}")
            if comp_parts:
                material_compositions[lang] = ", ".join(comp_parts)
    
    # Cotton detection
    if len(selected_materials) == 1 and selected_materials[0].lower() == "cotton":
        all_cotton = True
        for comp in components_data:
            comp_total = sum(m["pct"] for m in comp["materials"])
            if comp_total != 100 or comp["materials"][0]["mat"].lower() != "cotton":
                all_cotton = False
                break
        if all_cotton:
            cotton_value = "Y"
    
    if final_composition_text:
        st.markdown("### 📋 Final Composition (All Languages)")
        st.code(final_composition_text, language="text")
    
    # ============================================================
    # CARE INSTRUCTIONS UI
    # ============================================================
    st.markdown("### 🏷️ Care Instructions")
    
    care_instructions_df = care_data.get("care_instructions", pd.DataFrame())
    
    if "care_inst_list" not in st.session_state:
        st.session_state.care_inst_list = []
    
    care_inst_options = []
    if not care_instructions_df.empty:
        en_col = care_instructions_df.columns[0]
        care_inst_options = care_instructions_df[en_col].dropna().astype(str).tolist()
    
    if st.session_state.care_inst_list:
        st.write("**Selected Care Instructions:**")
        for idx, selected in enumerate(st.session_state.care_inst_list):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.write(f"• {selected}")
            with col2:
                if st.button("Remove", key=f"remove_care_{idx}"):
                    st.session_state.care_inst_list.pop(idx)
                    st.rerun()
    
    col_add_care, _ = st.columns([2, 3])
    with col_add_care:
        new_care_inst = st.selectbox("Add Care Instruction", options=[""] + care_inst_options, key="new_care_inst_select")
        if st.button("Add Care Instruction", key="add_care_inst_btn"):
            if new_care_inst and new_care_inst not in st.session_state.care_inst_list:
                st.session_state.care_inst_list.append(new_care_inst)
                st.rerun()
            elif new_care_inst in st.session_state.care_inst_list:
                st.warning("This instruction already added!")
    
    all_care_inst_translated = []
    for selected_care_inst in st.session_state.care_inst_list:
        inst_text = get_care_instruction_all_languages(selected_care_inst, care_instructions_df)
        if inst_text:
            all_care_inst_translated.append(inst_text)
    
    care_inst_translated = "\n\n".join(all_care_inst_translated) if all_care_inst_translated else ""
    
    if care_inst_translated:
        with st.expander("📋 Preview Care Instructions (All Languages)"):
            st.write(care_inst_translated)
    
    # ============================================================
    # DataFrame enrichment
    # ============================================================
    df['Dept'] = df['Item_classification'].apply(get_dept_value)
    if cotton_value == "Y":
        df['Cotton'] = cotton_value
    elif 'Cotton' in df.columns:
        df = df.drop(columns=['Cotton'])
    
    df['Collection'] = df.apply(lambda r: modify_collection(r['Collection'], r['Item_classification']), axis=1)
    
    # Format product translations with AL/MK compositions
    def format_product_translations(product_name, translation_row, material_compositions=None, components_data=None, comp_translations_df=None, use_advanced_mode=False):
        """Build multilingual product description with component names in AL/MK"""
        
        # সঠিক ভাষার অর্ডার
        language_order = [
            'AL', 'BG', 'BiH', 'CZ', 'DE', 'EE', 'ES', 'GR', 'HR', 'HU', 
            'IT', 'LT', 'LV', 'MK', 'PL', 'PT', 'RO', 'RS', 'SI', 'SK', 'UA'
        ]
        
        # Country suffixes
        country_suffixes = {
            'BiH': " Sastav materijala na ušivenoj etiketi.",
            'RS': " Sastav materijala nalazi se na ušivenoj etiketi.",
        }
        
        result = {}
        
        for lang in language_order:
            base_text = translation_row.get(lang, product_name)
            
            # AL এবং MK এর জন্য কম্পোজিশন যোগ করুন
            if lang in ['AL', 'MK']:
                if use_advanced_mode and components_data and comp_translations_df is not None:
                    # ADVANCED MODE: কম্পোনেন্টের নাম + কম্পোজিশন
                    comp_parts = []
                    for comp in components_data:
                        # কম্পোনেন্টের নাম ট্রান্সলেট করুন
                        comp_name = comp.get("name", "")
                        comp_translated = comp_name
                        if not comp_translations_df.empty:
                            row = comp_translations_df[comp_translations_df['EN'].astype(str).str.strip() == comp_name]
                            if not row.empty:
                                comp_translated = row.iloc[0].get(lang, comp_name)
                        
                        # ম্যাটেরিয়াল কম্পোজিশন
                        materials_parts = []
                        for mat in comp.get("materials", []):
                            if mat.get("mat") and mat.get("pct", 0) > 0:
                                # ম্যাটেরিয়াল ট্রান্সলেশন
                                mat_translated = mat["mat"]
                                if material_compositions is None:
                                    # Fallback: use material_translations_df
                                    t = material_translations_df[
                                        (material_translations_df['material'] == mat['mat']) & 
                                        (material_translations_df['language'] == lang)
                                    ]
                                    if not t.empty:
                                        mat_translated = t['translation'].iloc[0]
                                materials_parts.append(f"{mat['pct']}% {mat_translated}")
                        
                        materials_text = ", ".join(materials_parts)
                        comp_parts.append(f"{comp_translated} {materials_text}")
                    
                    if comp_parts:
                        base_text = f"{base_text}: {', '.join(comp_parts)}"
                elif material_compositions and lang in material_compositions:
                    # SIMPLE MODE: শুধু ম্যাটেরিয়াল (কম্পোনেন্টের নাম ছাড়া)
                    comp_text = material_compositions.get(lang, "")
                    if comp_text:
                        base_text = f"{base_text}: {comp_text}"
            
            # ES এর জন্য / দিয়ে Catalan যোগ করুন
            elif lang == 'ES':
                es_ca_text = translation_row.get('ES_CA', "")
                if es_ca_text and pd.notna(es_ca_text):
                    base_text = f"{base_text} / {es_ca_text}"
            
            # Country suffixes যোগ করুন
            if lang in country_suffixes:
                if not base_text.endswith('.'):
                    base_text += "."
                base_text += country_suffixes[lang]
            
            result[lang] = base_text
        
        # EN প্রথমে বসবে
        formatted = [f"|EN| {translation_row.get('EN', product_name)}"]
        
        # বাকি ভাষাগুলো অর্ডার অনুযায়ী যোগ হবে
        for lang in language_order:
            formatted.append(f"|{lang}| {result.get(lang, '')}")
        
        return " ".join(formatted)
    
    product_row = filtered[filtered['PRODUCT_NAME'] == product_type]
    if not product_row.empty:
        df['product_name'] = format_product_translations(
            product_type, 
            product_row.iloc[0], 
            material_compositions,
            components_data,
            comp_translations_df,
            use_advanced_mode  # এইটা যোগ করুন
        )
    else:
        df['product_name'] = ""
    
    df['washing_code'] = WASHING_CODES[washing_code_key]
    
    # ============================================================
    # PRICE LADDER + CSV EXPORT
    # ============================================================
    if pln_price is not None:
        currency_values = find_closest_price(pln_price)
        if currency_values:
            for cur in ['EUR', 'BGN', 'BAM', 'RON', 'CZK', 'UAH', 'MKD', 'RSD', 'HUF']:
                df[cur] = currency_values.get(cur, "")
            df['PLN'] = format_number(pln_price, 'PLN')
            df["Item_name_English"] = df["Item_name_EN"].apply(clean_item_name_english)
            
            # Composition এবং Care Instructions একসাথে
            combined_care = ""
            if final_composition_text and care_inst_translated:
                combined_care = f"{final_composition_text}\n\n{care_inst_translated}"
            elif final_composition_text:
                combined_care = final_composition_text
            elif care_inst_translated:
                combined_care = care_inst_translated
            
            df['Composition_Care'] = combined_care
            
            # SKU Name কলাম
            df['SKU_Name'] = df['Colour_SKU'].apply(lambda x: re.sub(r".*SKU\s*", "", x))
            # অথবা শুধু SKU নাম্বার চাইলে:
            # df['SKU_Name'] = df['Colour_SKU'].apply(lambda x: re.sub(r".*SKU\s*", "", x))

            final_cols = [
                "Order_ID", "Style", "Colour", "Supplier_product_code", "Item_classification",
                "Supplier_name", "today_date", "Collection", "Colour_SKU", "Style_Merch_Season",
                "Batch", "barcode", "washing_code", "EUR", "BGN", "BAM", "PLN", "RON", "CZK",
                "UAH", "MKD", "RSD", "HUF", "product_name", "Dept", "Item_name_English", "Season",
                "Composition_Care", "SKU_Name"  # নতুন কলাম
            ]
            
            # Optionally include Cotton column
            if 'Cotton' in df.columns and 'Cotton' not in final_cols:
                final_cols.append("Cotton")
            
            for col in final_cols:
                if col not in df.columns:
                    df[col] = ""
            
            st.success("✅ Done! Product data processed successfully.")
            st.subheader("✏️ Edit Before Download")
            edited_df = st.data_editor(df[final_cols])
            
            # ... rest of the code (CSV export)
            
            csv_buffer = StringIO()
            writer = pycsv.writer(csv_buffer, delimiter=';', quoting=pycsv.QUOTE_ALL)
            writer.writerow(final_cols)
            for row in edited_df.itertuples(index=False):
                writer.writerow(row)
            
            first_row_df = df.iloc[0]
            season_val = first_row_df.get("Season", "UNKNOWN").upper()
            all_skus = df['Colour_SKU'].apply(lambda x: re.sub(r".*SKU\s*", "", x)).tolist()
            sku_val = "_".join(all_skus) if all_skus else "UNKNOWN"
            supplier_code = first_row_df.get("Supplier_product_code", "UNKNOWN")
            style_val = first_row_df.get("Style", "UNKNOWN")
            custom_filename = f"PEPCO_{season_val}_{sku_val}_Swingtag {supplier_code}_00_{style_val}.csv"
            
            st.download_button(
                "📥 Download CSV",
                csv_buffer.getvalue().encode('utf-8-sig'),
                file_name=custom_filename,
                mime="text/csv"
            )
        else:
            st.warning("⚠️ Processing stopped - valid PLN price not found")


# ================================================================
#  PEPCO SECTION (Uploader + Reset)
# ================================================================
def pepco_section():
    st.subheader("📄 PEPCO Data Processing")
    
    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = 0
    
    cols = st.columns([1, 6])
    with cols[0]:
        def _reset_all():
            for k in list(st.session_state.keys()):
                if k.startswith(("ui_", "mat_", "pepco_", "comp_", "care_", "colour_", "simple_", "composition_")):
                    st.session_state.pop(k, None)
            st.session_state.uploader_key += 1
        
        st.button("🆕 Upload New File", on_click=_reset_all)
    
    uploaded_pdfs = st.file_uploader(
        "Upload PEPCO Data file (PDF)",
        type=["pdf"],
        key=f"pepco_uploader_{st.session_state.uploader_key}",
        accept_multiple_files=True
    )
    
    if uploaded_pdfs:
        if not isinstance(uploaded_pdfs, list):
            uploaded_pdfs = [uploaded_pdfs]
        
        primary_pdf = uploaded_pdfs[0]
        others = uploaded_pdfs[1:]
        
        other_ids = []
        for f in others:
            try:
                f.seek(0)
            except Exception:
                pass
            
            oid = extract_order_id_only(f)
            if oid:
                other_ids.append(oid)
            
            try:
                f.seek(0)
            except Exception:
                pass
        
        concatenated_ids = "+".join(other_ids) if other_ids else ""
        process_pepco_pdf(primary_pdf, extra_order_ids=concatenated_ids)


# ================================================================
#  HEADER RENDER
# ================================================================
def render_header():
    left, _ = st.columns([3, 10], vertical_alignment="center")
    with left:
        if os.path.exists(LOGO_SVG):
            st.image(LOGO_SVG, width=250)
        elif os.path.exists(LOGO_PNG):
            st.image(LOGO_PNG, width=250)
        else:
            st.markdown("<div style='font-size:40px'>🧾</div>", unsafe_allow_html=True)


# ================================================================
#  MAIN APP
# ================================================================
def main():
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    render_header()
    st.title("PEPCO Automation App")
    
    if not check_password():
        st.stop()
    
    pepco_section()
    
    st.markdown("---")
    st.caption("This app developed by Ovi")


if __name__ == "__main__":
    main()
