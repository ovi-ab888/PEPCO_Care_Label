# ================================================================
# PAGE CONFIG + IMPORTS + THEME + PASSWORD + CONSTANTS
# ================================================================

import streamlit as st
st.set_page_config(
    page_title="PEPCO",
    page_icon="🧾",
    layout="wide"
)

import fitz  # PyMuPDF
import pandas as pd
import re
from io import StringIO
import csv as pycsv
from datetime import datetime, timedelta
import os
import requests

# ================================================================
# LOGO & THEME
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
# PASSWORD CHECK SYSTEM
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
# CONSTANTS
# ================================================================
WASHING_CODES = {
    '1': '১২৩৪৫', '2': '১৪৭৮৫', '3': 'djnst', '4': 'djnpt', '5': 'djnqt',
    '6': 'djnqt', '7': 'gjnpt', '8': 'gjnpu', '9': 'gjnqt', '10': 'gjnqu',
    '11': 'ijnst', '12': 'ijnsu', '13': 'ijnpu', '14': 'ijnsv', '15': 'djnsw'
}

# ================================================================
# DATA LOADERS (শুধু প্রয়োজনীয়)
# ================================================================
@st.cache_data(ttl=600)
def load_care_composition_data():
    """Load 4 sheets/tables from Google Sheet"""
    
    BASE_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQtV5x4B3Sf_CCIMLCfvPtSP8nYru5BMAh5Xe4wWkqcrzZqT2cRJ7JYlvaHrsXql0h9Dnqohvq2mrKM/pub"
    
    sheets_config = {
        "comp_instructions": {"url": f"{BASE_URL}?gid=0&single=true&output=csv", "name": "Composition Instructions"},
        "materials": {"url": f"{BASE_URL}?gid=1935147264&single=true&output=csv", "name": "Materials"},
        "care_instructions": {"url": f"{BASE_URL}?gid=21483732&single=true&output=csv", "name": "Care Instructions"},
        "component_names": {"url": f"{BASE_URL}?gid=1020498108&single=true&output=csv", "name": "Component Names"}
    }
    
    result = {}
    for key, config in sheets_config.items():
        try:
            df = pd.read_csv(config["url"], encoding='utf-8')
            if not df.empty:
                result[key] = df
            else:
                result[key] = pd.DataFrame()
        except Exception:
            result[key] = pd.DataFrame()
    
    return result

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
# PDF EXTRACTION (শুধু প্রয়োজনীয়)
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
    return "UNKNOWN"

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

        # Item name EN (শুধু SKU_Name এর জন্য প্রয়োজন)
        m_item = re.search(r"Item\s*name\s*English\s*[:\.]{1,}\s*(.+)", full_text, re.IGNORECASE)
        if not m_item:
            m_item = re.search(r"Item\s*name\s*[:\.]{1,}\s*(.+?)\n", full_text, re.IGNORECASE)
        item_name_en = m_item.group(1).strip() if m_item else None

        style_code = re.search(r"\b\d{6}\b", page1)

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
                "Colour_SKU": f"{colour} • SKU {sku}",
                "barcode": barcode,
                "Item_name_EN": item_name_en or ""  # SKU_Name এর জন্য রাখা
            })
        return results
    except Exception as e:
        st.error(f"PDF error: {str(e)}")
        return None

# ================================================================
# MAIN PROCESSOR (সরলীকৃত)
# ================================================================
def process_pepco_pdf(uploaded_pdf, extra_order_ids: str | None = None):
    """Main pipeline: parse PDF, build DF, export CSV."""
    
    material_translations_df = load_material_translations()
    care_data = load_care_composition_data()
    comp_translations_df = load_component_translations()

    if not uploaded_pdf:
        st.error("No PDF uploaded")
        return

    result_data = extract_data_from_pdf(uploaded_pdf)
    if not result_data:
        return

    df = pd.DataFrame(result_data)
    
    if extra_order_ids:
        try:
            df['Order_ID'] = df['Order_ID'].astype(str) + "+" + extra_order_ids
        except Exception:
            pass

    # ============================================================
    # MATERIAL COMPOSITION UI
    # ============================================================
    st.markdown("### 🧵 Material Composition (%)")
    
    materials_df = care_data.get("materials", pd.DataFrame())
    comp_instructions_df = care_data.get("comp_instructions", pd.DataFrame())
    
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
                translations.append(str(val).strip())
        
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
                    translations.append(str(val).strip())
        
        return " / ".join(translations)
    
    def get_instruction_all_languages(inst_text):
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
    
    materials_options = []
    if not materials_df.empty:
        en_col = materials_df.columns[0]
        materials_options = materials_df[en_col].dropna().astype(str).tolist()
    if not materials_options:
        materials_options = ["Cotton", "Polyester", "Elastane", "Nylon", "Viscose", "Wool"]
    
    comp_inst_options = [""]
    if not comp_instructions_df.empty:
        en_col = comp_instructions_df.columns[0]
        comp_inst_options.extend(comp_instructions_df[en_col].dropna().astype(str).tolist())
    
    component_options = []
    if not comp_translations_df.empty:
        component_options = comp_translations_df["EN"].dropna().astype(str).tolist()
    if not component_options:
        component_options = ["Main fabric", "Outer fabric", "Lining", "Pocket bag", "Collar", "Cuff"]
    
    use_advanced_mode = st.toggle("🔧 Advanced Mode (Multiple Components)", value=False)
    
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
    
    final_composition_text = ""
    selected_materials = []
    components_data = []
    material_compositions = {}
    simple_comp_inst = ""
    
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
    
    composition_lines = []
    for comp in components_data:
        material_text = build_material_line(comp["materials"], use_translation=True)
        
        if use_advanced_mode:
            comp_translated = get_component_name_translations(comp["name"])
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
    
    final_composition_text = "\n\n".join(composition_lines)
    
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
    # Build Final DataFrame
    # ============================================================
    washing_code_key = '9'
    df['washing_code'] = WASHING_CODES[washing_code_key]
    
    # Composition + Care combined
    combined_care = ""
    if final_composition_text and care_inst_translated:
        combined_care = f"{final_composition_text}\n\n{care_inst_translated}"
    elif final_composition_text:
        combined_care = final_composition_text
    elif care_inst_translated:
        combined_care = care_inst_translated
    
    df['Composition_Care'] = combined_care
    
    # SKU Name from Colour_SKU
    df['SKU_Name'] = df['Colour_SKU'].apply(lambda x: re.sub(r".*SKU\s*", "", x))
    
    # ============================================================
    # FINAL COLUMNS (Only 11 columns)
    # ============================================================
    final_cols = [
        "Order_ID",
        "Style",
        "Colour",
        "Supplier_product_code",
        "Item_classification",
        "Supplier_name",
        "today_date",
        "barcode",
        "washing_code",
        "Composition_Care",
        "SKU_Name"
    ]
    
    # Ensure all columns exist
    for col in final_cols:
        if col not in df.columns:
            df[col] = ""
    
    # Keep only final columns
    df = df[final_cols]
    
    st.success("✅ Done! Product data processed successfully.")
    st.subheader("✏️ Edit Before Download")
    edited_df = st.data_editor(df)
    
    # ============================================================
    # CSV EXPORT
    # ============================================================
    csv_buffer = StringIO()
    writer = pycsv.writer(csv_buffer, delimiter=';', quoting=pycsv.QUOTE_ALL)
    writer.writerow(final_cols)
    
    for row in edited_df.itertuples(index=False):
        clean_row = tuple(str(x) if pd.notna(x) else "" for x in row)
        writer.writerow(clean_row)
    
    # Generate filename
    if not df.empty:
        first_row_df = df.iloc[0]
        sku_val = first_row_df.get("SKU_Name", "UNKNOWN")
        supplier_code = first_row_df.get("Supplier_product_code", "UNKNOWN")
        style_val = first_row_df.get("Style", "UNKNOWN")
        custom_filename = f"PEPCO_{sku_val}_CareLabel_{supplier_code}_00_{style_val}.csv"
    else:
        custom_filename = "PEPCO_export.csv"
    
    st.download_button(
        "📥 Download CSV",
        csv_buffer.getvalue().encode('utf-8-sig'),
        file_name=custom_filename,
        mime="text/csv"
    )

# ================================================================
# PEPCO SECTION (Uploader + Reset)
# ================================================================
def pepco_section():
    st.subheader("📄 PEPCO Data Processing")
    
    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = 0
    
    cols = st.columns([1, 6])
    with cols[0]:
        def _reset_all():
            for k in list(st.session_state.keys()):
                if k.startswith(("mat_", "pepco_", "comp_", "care_", "simple_", "composition_", "manual_colour_", "new_care_inst_select")):
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
# HEADER RENDER
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
# MAIN APP
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
