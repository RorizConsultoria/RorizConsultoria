"""
Dependências exigidas:
  pip install google-api-python-client google-cloud-secret-manager google-auth
"""
import streamlit as st
import pandas as pd
import os
import json
import re
import base64

from pathlib import Path
from google.cloud import secretmanager
from google.oauth2 import service_account
from google.api_core.exceptions import NotFound
from googleapiclient.discovery import build

# --- Configuração da Página ---
st.set_page_config(page_title="Dashboard de Cadastros", layout="centered")

# --- Fundo e logo ---
if Path("fundo.png").exists():
    with open("fundo.png", "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    st.markdown(
        f'''
        <style>
        .stApp {{
            background-image: url('data:image/png;base64,{encoded}');
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}
        </style>
        ''',
        unsafe_allow_html=True
    )

if Path("logo.png").exists():
    st.image("logo.png", width=150)

# --- Configurações ---
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "clear-incentive-410218")
SECRET_USERS = os.getenv("GCP_SECRET_ID_USERS", "USER_CREDENTIALS")
SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
SERVICE_ACCOUNT_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    str(Path(__file__).parent / "minha-sa-key.json")
)

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
if not SPREADSHEET_ID:
    st.error("Por favor defina a variável de ambiente SPREADSHEET_ID com o ID da sua planilha e reinicie o aplicativo.")
    st.stop()

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

    client = secretmanager.SecretManagerServiceClient(credentials=creds) if creds else secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
    try:
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except NotFound:
        return ""

users_json = get_secret(SECRET_USERS)
try:
    USERS = json.loads(users_json)
    if not isinstance(USERS, dict) or not USERS:
        raise ValueError
except Exception:
    USERS = {
        "Lara": "9096",
        "Edy": "1993",
        "Camilla": "1989",
        "Valeria": "Ze2024",
        "OutroUsuario": "Senha456"
    }

# --- Funções auxiliares ---
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
        with st.spinner("Gravando na planilha..."):
            return service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID,
                range=sheet_name,
                valueInputOption='USER_ENTERED',
                body={"values": [data]}
            ).execute()
    except Exception as e:
        st.error(f"Falha ao gravar na planilha: {e}")

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
        df = pd.DataFrame(vals[1:], columns=vals[0])
        df.columns = [col.strip() for col in df.columns]
        return df
    except Exception as e:
        st.error(f"Falha ao buscar dados da planilha: {e}")
        return pd.DataFrame()

def update_sheet(sheet_name: str, idx: int, data: list):
    try:
        service = get_sheets_service()
        row = idx + 2
        last_col = col_idx_to_letter(len(data) - 1)
        rng = f"{sheet_name}!A{row}:{last_col}{row}"
        with st.spinner("Atualizando registro..."):
            return service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=rng,
                valueInputOption='USER_ENTERED',
                body={"values": [data]}
            ).execute()
    except Exception as e:
        st.error(f"Falha ao atualizar planilha: {e}")

def display_login():
    st.title("Tela de Login")
    user = st.text_input("Usuário", key="username")
    pwd = st.text_input("Senha", type="password", key="password")
    if st.button("Entrar"):
        if USERS.get(user) == pwd:
            st.session_state['authenticated'] = True
            st.success(f"Bem-vindo, {user}!")
        else:
            st.error("Credenciais inválidas. Tente novamente.")

def display_dashboard():
    st.title("Dashboard de Cadastros")
    tabs = st.tabs(["Cadastro de Clientes", "🔎 Consulta", "✏️ Editar"])
    estados = ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA",
               "MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS",
               "RO","RR","SC","SP","SE","TO"]

    with tabs[0]:
        tipo = st.radio("Tipo de Cadastro", ["MEI", "Pessoa Física"])
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
                if st.form_submit_button('Cadastrar MEI'):
                    if not validate_cpf_cnpj(campos[6]) or not validate_cpf_cnpj(campos[7]):
                        st.error("CNPJ/CPF inválido.")
                    else:
                        save_to_sheet(campos, 'Sheet1')
                        st.success("Cadastro realizado com sucesso!")
            else:
                campos_pf = [
                    st.text_input('Nome Completo'),
                    st.text_input('Telefone'),
                    st.text_input('Email'),
                    st.text_input('CPF'),
                    st.selectbox('Estado', estados)
                ]
                if st.form_submit_button('Cadastrar Pessoa Física'):
                    if not validate_cpf_cnpj(campos_pf[3]):
                        st.error("CPF inválido.")
                    else:
                        save_to_sheet(campos_pf, 'Sheet2')
                        st.success("Cadastro de Pessoa Física salvo!")

    with tabs[1]:
        st.subheader("Cadastros MEI")
        df_mei = fetch_sheet("Sheet1")
        st.dataframe(df_mei)

        st.subheader("Cadastros Pessoa Física")
        df_pf = fetch_sheet("Sheet2")
        st.dataframe(df_pf)

    with tabs[2]:
        tipo = st.radio("Tipo de Registro", ["MEI", "Pessoa Física"])
        sheet_name = "Sheet1" if tipo == "MEI" else "Sheet2"
        df = fetch_sheet(sheet_name)
        if df.empty:
            st.info("Nenhum cadastro encontrado.")
        else:
            idx_map = {f"{i} - {df.iloc[i, 0]}": i for i in df.index}
            sel_label = st.selectbox("Selecione o registro", list(idx_map.keys()))
            idx = idx_map[sel_label]
            registro = df.loc[idx]
            with st.form("edit_form"):
                inputs = [
                    st.text_input(col, value=registro[col]) for col in df.columns
                ]
                if st.form_submit_button("Salvar alterações"):
                    update_sheet(sheet_name, idx, inputs)
                    st.success("Cadastro atualizado com sucesso!")

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if st.session_state['authenticated']:
    display_dashboard()
else:
    display_login()
