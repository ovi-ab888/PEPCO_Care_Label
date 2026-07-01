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
# PASSWORD CHECK SYSTEM (MULTIPLE PASSWORDS)
# ================================================================
def check_password():
    """Password gate supporting multiple passwords from secrets."""
    expected_passwords = None

    try:
        # সিক্রেটস থেকে পাসওয়ার্ড লিস্ট নিন
        expected_passwords = st.secrets.get("app_passwords", None)
    except Exception:
        expected_passwords = None

    # এনভায়রনমেন্ট ভেরিয়েবল থেকে নিন (একটি পাসওয়ার্ড)
    if expected_passwords is None:
        env_pass = os.environ.get("PEPCO_APP_PASSWORD")
        if env_pass:
            expected_passwords = [env_pass]

    if expected_passwords is None:
        st.error("App passwords not configured. Please set 'app_passwords' in secrets or PEPCO_APP_PASSWORD env var.")
        return False

    def _password_entered():
        entered = st.session_state.get("password", "")
        # চেক করুন এন্টার করা পাসওয়ার্ড লিস্টের কোনো একটির সাথে মেলে কিনা
        if entered in expected_passwords:
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
        st.error("❌ Your password is incorrect. Please contact Mr. Ovi")

    return False



# ================================================================
#  CONSTANTS & MAPPINGS
# ================================================================
WASHING_CODES = {
    '1': '১২৩৪৫', '2': '১৪৭৮৫', '3': 'djnst', '4': 'djnpt', '5': 'djnqt',
    '6': 'djnqt', '7': 'gjnpt', '8': 'gjnpu', '9': 'gjnqt', '10': 'gjnqu',
    '11': 'ijnst', '12': 'ijnsu', '13': 'ijnpu', '14': 'ijnsv', '15': 'djnsw'
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
#  HELPER FUNCTIONS - Department & Classification
# ================================================================

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


def get_size_options(item_classification):
    """
    Item Classification অনুযায়ী Size Options ফেরত দেয়
    """
    if not item_classification:
        return ["UNKNOWN"]
    
    ic = item_classification.lower()
    
    # Baby sizes (0-24 months)
    if 'baby' in ic:
        return ['3/6', '6/9', '9/12', '12/18', '18/24', '24/36']
    
    # Younger sizes (3-8 years)
    elif 'younger' in ic:
        return ['3-4 yrs', '4-5 yrs', '5-6 yrs', '6-7 yrs', '7-8 yrs', '8-9 yrs']
    
    # Older sizes - Sheet অনুযায়ী ২ ধরনের Size
    elif 'older' in ic:
        # Check যদি Top Size হয় (T-shirt, Shirt, Top ইত্যাদি)
        if 't-shirt' in ic or 'shirt' in ic or 'top' in ic or 'blouse' in ic:
            # Top Size
            return [
                '9 - 10 yrs',   # 134/140 cm
                '11 - 12 yrs',  # 146/152 cm
                '13 - 14 yrs',  # 158/164 cm
                '15 yrs'        # 170 cm
            ]
        else:
            # Bottom Size (Jog suit, Pants, Leggings, Outerwear ইত্যাদি)
            return [
                '9 yrs',    # 134 cm
                '10 yrs',   # 140 cm
                '11 yrs',   # 146 cm
                '12 yrs',   # 152 cm
                '13 yrs',   # 158 cm
                '14 yrs',   # 164 cm
                '15 yrs'    # 170 cm
            ]
    
    # Ladies/Mens sizes
    elif 'ladies' in ic or 'mens' in ic:
        return ['XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL']
    
    # Default
    return ['UNKNOWN']


def map_pdf_size_to_csv_size(pdf_size, item_classification):
    """
    PDF Size কে CSV Size এ কনভার্ট করা
    """
    if not pdf_size or not item_classification:
        return pdf_size
    
    ic = item_classification.lower()
    pdf_size_str = str(pdf_size).strip()
    
    # Baby sizes mapping
    if 'baby' in ic:
        size_map = {
            '3/6': '74 cm',
            '6/9': '80 cm',
            '9/12': '86 cm',
            '12/18': '92 cm',
            '18/24': '98 cm',
            '24/36': '104 cm'
        }
        return size_map.get(pdf_size_str, pdf_size_str)
    
    # Younger sizes mapping
    elif 'younger' in ic:
        size_map = {
            '3-4 yrs': '104 cm',
            '4-5 yrs': '110 cm',
            '5-6 yrs': '116 cm',
            '6-7 yrs': '122 cm',
            '7-8 yrs': '128 cm',
            '8-9 yrs': '134 cm'
        }
        return size_map.get(pdf_size_str, pdf_size_str)
    
    # Older sizes mapping - Sheet অনুযায়ী ২ ধরনের Size
    elif 'older' in ic:
        # Top Size mapping
        if 't-shirt' in ic or 'shirt' in ic or 'top' in ic or 'blouse' in ic:
            size_map = {
                '9 - 10 yrs': '134/140 cm',
                '11 - 12 yrs': '146/152 cm',
                '13 - 14 yrs': '158/164 cm',
                '15 yrs': '170 cm'
            }
        else:
            # Bottom Size mapping
            size_map = {
                '9 yrs': '134 cm',
                '10 yrs': '140 cm',
                '11 yrs': '146 cm',
                '12 yrs': '152 cm',
                '13 yrs': '158 cm',
                '14 yrs': '164 cm',
                '15 yrs': '170 cm'
            }
        return size_map.get(pdf_size_str, pdf_size_str)
    
    # Ladies/Mens sizes mapping
    elif 'ladies' in ic or 'mens' in ic:
        size_map = {
            'XS': 'XS',
            'S': 'S',
            'M': 'M',
            'L': 'L',
            'XL': 'XL',
            'XXL': 'XXL',
            '3XL': '3XL'
        }
        return size_map.get(pdf_size_str, pdf_size_str)
    
    return pdf_size_str


def get_selected_sizes(from_size, to_size, size_options):
    """From এবং To এর মধ্যে সব Size বের করে"""
    if from_size not in size_options or to_size not in size_options:
        return [size_options[0]] if size_options else []
    
    from_index = size_options.index(from_size)
    to_index = size_options.index(to_size)
    
    if from_index <= to_index:
        return size_options[from_index:to_index + 1]
    else:
        return size_options[to_index:from_index + 1]


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

        # Item_name_EN
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
                "barcode": barcode,
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
    """PDF থেকে ডাটা নিয়ে CSV বানাও"""
    
    # ডাটা লোড করি
    material_translations_df = load_material_translations()
    care_data = load_care_composition_data()
    comp_translations_df = load_component_translations()

    if not uploaded_pdf:
        return

    # PDF থেকে ডাটা এক্সট্র্যাক্ট করি
    result_data = extract_data_from_pdf(uploaded_pdf)
    if not result_data:
        return

    df = pd.DataFrame(result_data)

    # একাধিক PDF থাকলে Order ID যোগ করি
    if extra_order_ids:
        df['Order_ID'] = df['Order_ID'].astype(str) + "+" + extra_order_ids

    # ============================================================
    # UI - Select Department + Washing Code + Select Size (1 line)
    # ============================================================
    
    first_row = result_data[0]
    pdf_item_class = first_row.get("Item_classification", "")
    
    # Department Options
    dept_options = ["Baby Boy", "Baby Girl", "Boys", "Girls", "Women", "Mens"]
    default_dept_label = map_item_class_to_dept_label(pdf_item_class)
    default_dept_index = 0
    if default_dept_label and default_dept_label in dept_options:
        default_dept_index = dept_options.index(default_dept_label)
    
    # Size Options
    size_options = get_size_options(pdf_item_class)
    
    # 3 columns in 1 line
    col1, col2, col3 = st.columns(3)
    
    with col1:
        selected_dept = st.selectbox(
            "Select Department", 
            options=dept_options, 
            index=default_dept_index,
            key="ui_dept"
        )
    
    with col2:
        washing_options = list(WASHING_CODES.keys())
        washing_default_index = washing_options.index('9') if '9' in washing_options else 0
        washing_code_key = st.selectbox(
            "Select Washing Code", 
            options=washing_options, 
            index=washing_default_index,
            key="ui_wash"
        )
    
    with col3:
        # Size Range Selection - 2 Dropdowns in one column
        st.markdown("##### Select Size Range")
        size_col1, size_col2 = st.columns(2)
        
        with size_col1:
            from_size = st.selectbox(
                "From",
                options=size_options,
                index=0,
                key="ui_size_from"
            )
        
        with size_col2:
            to_size = st.selectbox(
                "To",
                options=size_options,
                index=len(size_options) - 1 if size_options else 0,
                key="ui_size_to"
            )
        
        # Selected sizes
        selected_pdf_sizes = get_selected_sizes(from_size, to_size, size_options)
        selected_csv_sizes = []
        for pdf_size in selected_pdf_sizes:
            csv_size = map_pdf_size_to_csv_size(pdf_size, pdf_item_class)
            selected_csv_sizes.append(csv_size)
        
        # Show selected sizes info
        if selected_pdf_sizes:
            st.caption(f"📌 {', '.join(selected_csv_sizes)}")

    # ============================================================
    # Material Composition
    # ============================================================
    st.markdown("### 🧵 Material Composition (%)")
    
    materials_df = care_data.get("materials", pd.DataFrame())
    comp_instructions_df = care_data.get("comp_instructions", pd.DataFrame())
    
    # Material options
    materials_options = []
    if not materials_df.empty:
        en_col = materials_df.columns[0]
        materials_options = materials_df[en_col].dropna().astype(str).tolist()
    if not materials_options:
        materials_options = ["Cotton", "Polyester", "Elastane", "Nylon", "Viscose", "Wool"]
    
    # Component options
    component_options = []
    if not comp_translations_df.empty:
        component_options = comp_translations_df["EN"].dropna().astype(str).tolist()
    if not component_options:
        component_options = ["Main fabric", "Outer fabric", "Lining", "Pocket bag", "Collar", "Cuff"]
    
    # Mode toggle
    use_advanced_mode = st.toggle("🔧 Advanced Mode (Multiple Components)", value=False)
    
    # Session state
    if "composition_blocks" not in st.session_state:
        st.session_state.composition_blocks = []
    
    if not st.session_state.composition_blocks:
        st.session_state.composition_blocks.append({
            "component_name": "Main fabric",
            "comp_inst": "",
            "materials": [{"mat": "", "pct": 0}]
        })
    
    # Helper functions
    def get_material_all_languages(mat_name, pct):
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
                text = str(val).strip()
                if text:
                    text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
                translations.append(text)
        return f"{pct}% {'/ '.join(translations)}"
    
    def get_component_name_translations(comp_name):
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
                    text = str(val).strip()
                    if text:
                        text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
                    translations.append(text)
        return "/ ".join(translations)
    
    def get_care_instruction_all_languages(inst_text, care_instructions_df):
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
                text = str(val).strip()
                if text:
                    text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
                translations.append(text)
        return "/ ".join(translations)
    
    def build_material_line(materials, use_translation=True):
        parts = []
        for m in materials:
            if m["mat"] and m["pct"] > 0:
                if use_translation:
                    mat_text = get_material_all_languages(m["mat"], m["pct"])
                    if mat_text:
                        mat_text = mat_text[0].upper() + mat_text[1:] if len(mat_text) > 1 else mat_text.upper()
                else:
                    mat_text = f"{m['pct']}% {m['mat']}"
                parts.append(mat_text)
        return "\n\n".join(parts)
    
    # Render blocks
    components_data = []
    selected_materials = []
    final_composition_text = ""
    
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
    
    # Build final composition
    composition_lines = []
    for comp in components_data:
        material_text = build_material_line(comp["materials"], use_translation=True)
        if use_advanced_mode:
            comp_translated = get_component_name_translations(comp["name"])
            line = f"{comp_translated}:\n\n{material_text}"
        else:
            line = material_text
        composition_lines.append(line)
    
    final_composition_text = "\n\n".join(composition_lines)
    
    # Material compositions for AL/MK
    material_compositions = {}
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

    # ============================================================
    # CARE INSTRUCTIONS
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

    # ============================================================
    # CSV তৈরি
    # ============================================================
    
    # Size যোগ করুন (UI থেকে সিলেক্ট করা)
    # প্রতিটি Barcode এর সাথে সাইক্লিকভাবে Size ম্যাপ করা
    size_count = len(selected_csv_sizes)
    if size_count > 0:
        df['Size'] = [selected_csv_sizes[i % size_count] for i in range(len(df))]
    else:
        df['Size'] = "UNKNOWN"
    
    # Dept যোগ করুন
    df['Dept'] = df['Item_classification'].apply(get_dept_value)
    
    df['washing_code'] = WASHING_CODES[washing_code_key]
    
    # কম্পোজিশন + কেয়ার ইন্সট্রাকশন
    combined_care = ""
    if final_composition_text and care_inst_translated:
        combined_care = f"{final_composition_text}\n\n{care_inst_translated}"
    elif final_composition_text:
        combined_care = final_composition_text
    elif care_inst_translated:
        combined_care = care_inst_translated

    # Skupljanje লাইন যোগ করুন
    shrinkage_line = "Skupljanje:  po dužini: 4%, po širini 4%"

    # Bangladesh/Produced by লাইন যোগ করুন
    bangladesh_line = """Made in Bangladesh/ Vendi i Origjinës: Bangladesh/ Произведено в Бангладеш/ Fabricado en Bangladesh/ Κατασκευάζεται στην Μπαγκλαντές/ Pagaminta Bangladeše/ Ražots Bangladešā/ Wyprodukowano w Bangladeszu/ Произведено во Бангладеш/ Proizvedeno u Bangladešu/ Zemlja izvoza: EU/ Виготовлено в Бангладеш.

Produced by/ Prodhuesi/ Производител/ Výrobce/ Hersteller/ Tootja/ Fabricante/
Fabricant/ Κατασκευαστής/ Proizvođač/ Gyártó/ Produttore/ Gamintojas/ Ražotājs/ Producent/ Producător/ Izdelovalec/ Výrobca/ Виробник:


Pepco Poland Sp. z o.o., ul. Strzeszyńska 73A, 60-479 Poznań Poland, klient@pepco.eu, NIP (NIF) 782-21-31-157.
Пепко Полска Сп. з o.o., ул. Стрзесзинска 73А, 60-479 Познан. Пепко Польска Сп. з.о.о., вул Стшешинська 73A, 60-479 Познань. Na tržište RH stavlja: Pepco Croatia d.o.o., D. T. Gavrana 11, 10020 Zagreb.
Uvoznik za Srbiju: Pepco d.o.o., Pariske komune 22, 11070 Beograd-Novi Beograd. klijent.rs@pepco.eu
Διανομέας: Pepco Greece Μονοπρόσωπη Ι.Κ.Ε., Πέτρου Ράλλη 97, 182 33, Αγ. Ιωάννης Ρέντης. Uvoznik za BiH: Pepco B-H d.o.o., ulica Skenderpašina br. 1, Opština Centar Sarajevo, 71 000 Sarajevo. klijent.ba@pepco.eu
Увозник/ Importuesi: ПЕПЦО ДООЕЛ Скопје, Ул. НАУМ НАУМОВСКИ - БОРЧЕ Бр.40/5-8 СКОПЈЕ - ЦЕНТАР ЦЕНТАР/ PEPCO DOOEL Shkup, Rruga Naum Naumovski-Borche Nr. 40/5-8, Shkup – Qendër, Maqedonia e Veriut. Імпортер: ТОВАРИСТВО З ОБМЕЖЕНОЮ ВІДПОВІДАЛЬНІСТЮ “ПЕПКО УКРАЇНА” вул. Загородня, 15,
м. Київ, 03150, Україна, customer@pepco.eu"""

    # সবকিছু একসাথে যোগ করুন
    if combined_care:
        combined_care = f"{combined_care}\n\n{shrinkage_line}\n\n{bangladesh_line}"
    else:
        combined_care = f"{shrinkage_line}\n\n{bangladesh_line}"

    df['Composition_Care'] = combined_care

    # SKU_Name তৈরি - barcode থেকে
    df['SKU_Name'] = df['barcode'].astype(str)

    # CSV এর কলাম
    final_cols = [
        "Order_ID", "Style", "Colour", "Supplier_product_code", "Item_classification",
        "Supplier_name", "today_date",
        "barcode", "Size", "SKU_Name", "washing_code",
        "Season", "Composition_Care", "Dept"
    ]

    for col in final_cols:
        if col not in df.columns:
            df[col] = ""

    st.success("✅ Done! Product data processed successfully.")
    st.subheader("Edit Before Download")
    edited_df = st.data_editor(df[final_cols])

    # CSV Download
    csv_buffer = StringIO()
    writer = pycsv.writer(csv_buffer, delimiter=';', quoting=pycsv.QUOTE_ALL)
    writer.writerow(final_cols)
    for row in edited_df.itertuples(index=False):
        writer.writerow(row)

    first_row_df = df.iloc[0]
    season_val = first_row_df.get("Season", "UNKNOWN").upper()
    all_skus = df['SKU_Name'].tolist()
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
