from pathlib import Path
import streamlit as st
import pandas as pd
import os
import json
import re
import base64
from datetime import datetime
from google.cloud import secretmanager
from google.oauth2 import service_account
from google.api_core.exceptions import NotFound
from googleapiclient.discovery import build

# --- Aparência da página ---
st.set_page_config(page_title="Dashboard de Cadastros", page_icon="📊", layout="centered", initial_sidebar_state="collapsed")

# --- CSS personalizado ---
st.markdown("""
<style>
div.stButton > button:first-child {
    background-color: #1f3c88;
    color: white;
    border-radius: 5px;
    padding: 0.5em 1.2em;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.2);
    transition: 0.3s;
}
div.stButton > button:first-child:hover {
    background-color: #2e86de;
    box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
}
@keyframes shake {
    0% { transform: translateX(0px); }
    25% { transform: translateX(-5px); }
    50% { transform: translateX(5px); }
    75% { transform: translateX(-5px); }
    100% { transform: translateX(0px); }
}
</style>
""", unsafe_allow_html=True)

# --- Fundo personalizado ---
if Path("fundo.png").exists():
    with open("fundo.png", "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    st.markdown(f"""
        <style>
        .stApp {{
            background-image: url("data:image/png;base64,{encoded}");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}
        </style>
    """, unsafe_allow_html=True)

# --- Logo ---
if Path("logo.png").exists():
    st.image("logo.png", width=150)

# --- Segredos e credenciais ---
for key in ["GOOGLE_SERVICE_ACCOUNT_JSON", "SPREADSHEET_ID", "USER_CREDENTIALS"]:
    if key in st.secrets:
        os.environ[key] = st.secrets[key]

SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(Path(__file__).parent / "minha-sa-key.json"))
DEFAULT_PROJECT_ID = "lararorizinc"
PROJECT_ID = DEFAULT_PROJECT_ID

if SERVICE_ACCOUNT_JSON and SERVICE_ACCOUNT_JSON.strip().startswith("{"):
    try:
        info = json.loads(SERVICE_ACCOUNT_JSON)
        PROJECT_ID = info.get("project_id", DEFAULT_PROJECT_ID)
    except:
        pass

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

@st.cache_data
def get_secret(secret_id: str) -> str:
    env_val = os.getenv(secret_id)
    if env_val:
        return env_val
    creds = None
    if SERVICE_ACCOUNT_JSON and SERVICE_ACCOUNT_JSON.strip().startswith("{"):
        info = json.loads(SERVICE_ACCOUNT_JSON)
        creds = service_account.Credentials.from_service_account_info(info)
    elif os.path.isfile(SERVICE_ACCOUNT_FILE):
        creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
    client = secretmanager.SecretManagerServiceClient(credentials=creds)
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
    try:
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except NotFound:
        return ""
    except:
        return ""

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID") or get_secret("SPREADSHEET_ID")
if not SPREADSHEET_ID:
    st.error("SPREADSHEET_ID não encontrado.")
    st.stop()

users_json = os.getenv("USER_CREDENTIALS") or get_secret("USER_CREDENTIALS")
try:
    USERS = json.loads(users_json)
    if not isinstance(USERS, dict) or not USERS:
        raise ValueError
except:
    USERS = {"admin": "1234"}

# --- Utilitários Google Sheets ---
def col_idx_to_letter(idx: int) -> str:
    letters = ''
    while idx >= 0:
        letters = chr(ord('A') + (idx % 26)) + letters
        idx = idx // 26 - 1
    return letters

def validate_cpf_cnpj(value: str) -> bool:
    return bool(re.fullmatch(r"\d{11}|\d{14}", re.sub(r"\D", "", value)))

def get_sheets_service():
    if SERVICE_ACCOUNT_JSON and SERVICE_ACCOUNT_JSON.strip().startswith("{"):
        info = json.loads(SERVICE_ACCOUNT_JSON)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds)

def save_to_sheet(data: list, sheet_name: str):
    try:
        service = get_sheets_service()
        data.append(datetime.now().strftime('%d/%m/%Y %H:%M'))
        return service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=sheet_name,
            valueInputOption='USER_ENTERED',
            body={"values": [data]}
        ).execute()
    except Exception as e:
        st.error(f"Erro ao gravar: {e}")

def fetch_sheet(sheet_name: str) -> pd.DataFrame:
    try:
        service = get_sheets_service()
        res = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_name}!A1:Z"
        ).execute()
        vals = res.get('values', [])
        if len(vals) < 2:
            return pd.DataFrame()
        return pd.DataFrame(vals[1:], columns=vals[0])
    except:
        return pd.DataFrame()

def update_sheet(sheet_name: str, idx: int, data: list):
    try:
        df = fetch_sheet(sheet_name)
        if len(data) != len(df.columns):
            st.warning("⚠️ Número de colunas no formulário não corresponde à planilha.")
            return
        service = get_sheets_service()
        row = idx + 2
        last_col = col_idx_to_letter(len(data) - 1)
        rng = f"{sheet_name}!A{row}:{last_col}{row}"
        return service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=rng,
            valueInputOption='USER_ENTERED',
            body={"values": [data]}
        ).execute()
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}")

# --- Interface ---
def display_login():
    st.title("Login 🔐")
    with st.form("login_form"):
        user = st.text_input("Usuário")
        pwd = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if USERS.get(user) == pwd:
                st.session_state['authenticated'] = True
                st.session_state['username'] = user
                st.success("🎉 Login bem-sucedido!")
                st.rerun()
            else:
                st.error("🚫 Usuário ou senha incorretos.")
                st.markdown("<div style='animation: shake 0.3s;'>❌</div>", unsafe_allow_html=True)

def display_dashboard():
    st.markdown(f"""
<div style='
    background-color: #1f3c88;
    padding: 0.6em 1em;
    border-radius: 8px;
    margin-bottom: 1.2em;
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: white;
    font-size: 1.1em;
    box-shadow: 1px 1px 5px rgba(0,0,0,0.1);
'>
    <span>📊 <strong>Dashboard de Cadastros</strong></span>
    <span style='font-size: 0.95em;'>Olá, {st.session_state.get("username", "usuário")} 👋</span>
</div>
""", unsafe_allow_html=True)


    tabs = st.tabs(["Cadastro", "🔎 Consulta", "✏️ Editar"])
    estados = ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"]

    # --- Cadastro ---
    with tabs[0]:
        tipo = st.radio("Tipo", ["MEI", "Pessoa Física"])
        with st.form("cad_form"):
            if tipo == "MEI":
                campos = [
                    st.text_input('Nome da Empresa'),
                    st.text_input('Nome do Responsável'),
                    st.text_input('Telefone'),
                    st.text_input('Email'),
                    st.text_input('Senha Gov.br'),
                    st.selectbox('Estado', estados),
                    st.text_input('CNPJ'),
                    st.text_input('CPF'),
                    st.selectbox('Status MEI', ['Ativo', 'Baixado'])
                ]
                if st.form_submit_button('Cadastrar'):
                    if not validate_cpf_cnpj(campos[6]) or not validate_cpf_cnpj(campos[7]):
                        st.error("CNPJ ou CPF inválido.")
                    else:
                        save_to_sheet(campos, "Sheet1")
                        st.success("Cadastro MEI salvo!")
                        st.rerun()
            else:
                campos_pf = [
                    st.text_input('Nome Completo'),
                    st.text_input('Telefone'),
                    st.text_input('Email'),
                    st.text_input('CPF'),
                    st.selectbox('Estado', estados)
                ]
                if st.form_submit_button('Cadastrar'):
                    if not validate_cpf_cnpj(campos_pf[3]):
                        st.error("CPF inválido.")
                    else:
                        save_to_sheet(campos_pf, "Sheet2")
                        st.success("Cadastro Pessoa Física salvo!")
                        st.rerun()

    # --- Consulta ---
    with tabs[1]:
        st.subheader("🔍 Consulta de Cadastros")

        with st.expander("📁 Cadastros MEI"):
            df_mei = fetch_sheet("Sheet1")
            if not df_mei.empty:
                col1, col2, col3 = st.columns(3)
                estado_filtro = col1.selectbox("Filtrar por Estado", ["Todos"] + sorted(df_mei['Estado'].unique()))
                status_filtro = col2.selectbox("Status MEI", ["Todos"] + sorted(df_mei['Status MEI'].unique()))
                nome_filtro = col3.text_input("Buscar por nome (MEI)")

                if estado_filtro != "Todos":
                    df_mei = df_mei[df_mei['Estado'] == estado_filtro]
                if status_filtro != "Todos":
                    df_mei = df_mei[df_mei['Status MEI'] == status_filtro]
                if nome_filtro:
                    df_mei = df_mei[df_mei['Nome do Responsável'].str.contains(nome_filtro, case=False, na=False)]

                st.markdown(f"🔢 <b>Total de registros encontrados: {len(df_mei)}</b>", unsafe_allow_html=True)
                st.dataframe(df_mei)
            else:
                st.info("Nenhum cadastro MEI encontrado.")

        with st.expander("👤 Cadastros Pessoa Física"):
            df_pf = fetch_sheet("Sheet2")
            if not df_pf.empty:
                col1, col2 = st.columns(2)
                estado_pf = col1.selectbox("Filtrar por Estado (PF)", ["Todos"] + sorted(df_pf['Estado'].unique()))
                nome_pf = col2.text_input("Buscar por nome (PF)")

                if estado_pf != "Todos":
                    df_pf = df_pf[df_pf['Estado'] == estado_pf]
                if nome_pf:
                    df_pf = df_pf[df_pf['Nome Completo'].str.contains(nome_pf, case=False, na=False)]

                st.markdown(f"🔢 <b>Total de registros encontrados: {len(df_pf)}</b>", unsafe_allow_html=True)
                st.dataframe(df_pf)
            else:
                st.info("Nenhum cadastro de Pessoa Física encontrado.")

    # --- Edição ---
    with tabs[2]:
        tipo = st.radio("Editar tipo", ["MEI", "Pessoa Física"])
        sheet_name = "Sheet1" if tipo == "MEI" else "Sheet2"
        df = fetch_sheet(sheet_name)
        if df.empty:
            st.info("Nenhum dado encontrado.")
        else:
            idx_map = {f"{i} - {df.iloc[i, 0]}": i for i in df.index}
            sel_label = st.selectbox("Selecione o registro", list(idx_map.keys()))
            idx = idx_map[sel_label]
            registro = df.loc[idx]
            with st.form("edit_form"):
                inputs = [st.text_input(col, value=registro[col]) for col in df.columns]
                if st.form_submit_button("Salvar alterações"):
                    update_sheet(sheet_name, idx, inputs)
                    st.success("Atualização realizada.")
                    st.rerun()

# --- Execução ---
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if st.session_state['authenticated']:
    display_dashboard()
else:
    display_login()
