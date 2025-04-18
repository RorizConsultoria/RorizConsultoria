import streamlit as st
import pandas as pd
from datetime import datetime
import os
import pickle
import json
import base64
import io

from PIL import Image, ImageDraw, ImageFont
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.cloud import secretmanager

# --- Configuração da Página ---
st.set_page_config(layout="wide")

# --- Credenciais (usuários e senhas) ---
USERS = {
    "Lara": "9096",
    "Edy": "1993",
    "Camilla": "1989",
    "Valeria": "Ze2024",
    "OutroUsuario": "Senha456"
}

# --- Constantes e Escopos ---
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']
API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyC60Hd8LEQvj8-c25rHcWFv_lZSyrvmyGY")
TOKEN_PICKLE = 'token.pickle'
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", '1JhRsHpySEpJbefsZTbTjlh3QuyZUzFtx1OMuHDLChx4')
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "elo-solutions")
SECRET_ID = os.getenv("GCP_SECRET_ID", "CLIENT_SECRETS")

# --- Utilitários ---
def get_base64_of_bin_file(bin_file: str) -> str:
    try:
        with open(bin_file, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return ""


def set_bg_from_local(image_file: str):
    b64 = get_base64_of_bin_file(image_file)
    if b64:
        st.markdown(f"""
        <style>
        .stApp {{ background-image: url('data:image/png;base64,{b64}'); background-size: cover; background-attachment: fixed; }}
        </style>
        """, unsafe_allow_html=True)


def format_currency_br(value: float) -> str:
    return "R$ {:,.2f}".format(value).replace(",", "TMP").replace(".", ",").replace("TMP", ".")

# --- Google Authentication & Sheets Helpers ---
def get_client_secrets():
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{PROJECT_ID}/secrets/{SECRET_ID}/versions/latest"
        resp = client.access_secret_version(request={"name": name})
        return json.loads(resp.payload.data.decode())
    except Exception as e:
        st.error(f"Erro ao acessar secret: {e}")
        return None


def authenticate_google():
    creds = None
    if os.path.exists(TOKEN_PICKLE):
        with open(TOKEN_PICKLE, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                st.error(f"Falha ao atualizar token: {e}")
        else:
            config = get_client_secrets()
            if not config:
                return None
            flow = InstalledAppFlow.from_client_config(config, SCOPES)
            flow.redirect_uri = 'http://localhost:8501'
            creds = flow.run_local_server(port=8501)
        with open(TOKEN_PICKLE, 'wb') as token:
            pickle.dump(creds, token)
    return creds


def save_to_sheet(data: list, sheet_name='Sheet1'):
    creds = authenticate_google()
    if not creds:
        return None
    service = build('sheets', 'v4', credentials=creds, developerKey=API_KEY)
    return service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=sheet_name,
        valueInputOption='USER_ENTERED',
        body={"values": [data]}
    ).execute()


def fetch_sheet(sheet_name='Sheet1') -> pd.DataFrame:
    creds = authenticate_google()
    if not creds:
        return pd.DataFrame()
    service = build('sheets', 'v4', credentials=creds, developerKey=API_KEY)
    res = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!A1:Z"
    ).execute()
    vals = res.get('values', [])
    if len(vals) < 2:
        return pd.DataFrame()
    return pd.DataFrame(vals[1:], columns=vals[0])


def update_sheet(sheet_name: str, idx: int, data: list):
    creds = authenticate_google()
    if not creds:
        return None
    service = build('sheets', 'v4', credentials=creds, developerKey=API_KEY)
    row_num = idx + 2
    last_col = chr(ord('A') + len(data) - 1)
    rng = f"{sheet_name}!A{row_num}:{last_col}{row_num}"
    return service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=rng,
        valueInputOption='USER_ENTERED',
        body={"values": [data]}
    ).execute()

# --- UI Components ---
def display_login():
    st.title("Tela de Login")
    set_bg_from_local("fundo.png")
    user = st.text_input("Usuário", key="username")
    pwd = st.text_input("Senha", type="password", key="password")
    if st.button("Entrar"):
        if USERS.get(user) == pwd:
            st.session_state['authenticated'] = True
        else:
            st.error("Credenciais inválidas.")


def display_dashboard():
    if os.path.exists("logo.png"): st.image("logo.png", width=200)
    st.title("Dashboard de Cadastros")
    # Define três abas: Cadastro, Consulta e Editar
    tabs = st.tabs(["Cadastro de Clientes", "🔎 Consulta", "✏️ Editar"])
    states = ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"]

    # Aba Cadastro de Clientes
    with tabs[0]:
        tipo = st.radio("Tipo de Cadastro", ["MEI","Pessoa Física"], key="cad_tipo")
        with st.form("cad_form"):
            if tipo == "MEI":
                ne = st.text_input('Nome da Empresa', key="nm_e")
                nr = st.text_input('Nome do Responsável', key="nr")
                tel = st.text_input('Telefone', key="tel")
                em = st.text_input('Email', key="em")
                sg = st.text_input('Senha Gov.br', key="sg")
                est = st.selectbox('Estado', states, key="est")
                cn = st.text_input('CNPJ', key="cn")
                cf = st.text_input('CPF', key="cf")
                sm = st.selectbox('Status MEI', ['Ativo','Baixado'], key="sm")
                sb = st.form_submit_button('Cadastrar MEI')
                if sb:
                    authenticate_google()
                    save_to_sheet([ne,nr,tel,em,sg,est,cn,cf,sm], 'Sheet1')
                    st.success('MEI cadastrado com sucesso!')
            else:
                pf = [
                    st.text_input('Nome Completo', key="pf_n"),
                    st.text_input('Telefone', key="pf_t"),
                    st.text_input('Email', key="pf_e"),
                    st.text_input('RG', key="pf_rg"),
                    st.text_input('CPF', key="pf_cf"),
                    st.text_input('Senha Gov.br', key="pf_sg"),
                    st.text_input('Endereço', key="pf_en"),
                    st.text_input('Cidade', key="pf_c"),
                    st.text_input('CEP', key="pf_cep"),
                    st.selectbox('Estado', states, key="pf_est"),
                    st.text_input('Chave Pix', key="pf_pix"),
                    st.selectbox('Bens Imóveis', ['Sim','Não'], key="pf_bi"),
                    st.selectbox('Bens Móveis', ['Sim','Não'], key="pf_bm"),
                    st.selectbox('Dependentes', ['Sim','Não'], key="pf_dep")
                ]
                sb2 = st.form_submit_button('Cadastrar PF')
                if sb2:
                    authenticate_google()
                    save_to_sheet(pf, 'Sheet2')
                    st.success('Pessoa Física cadastrada com sucesso!')

    # Aba Consulta de Cadastros
    with tabs[1]:
        df_mei = fetch_sheet('Sheet1')
        df_pf = fetch_sheet('Sheet2')
        st.header('Cadastros MEI')
        if not df_mei.empty:
            st.dataframe(df_mei)
        else:
            st.info('Nenhum MEI cadastrado.')
        st.header('Cadastros Pessoa Física')
        if not df_pf.empty:
            st.dataframe(df_pf)
        else:
            st.info('Nenhuma Pessoa Física cadastrada.')

    # Aba Editar Cadastros
    with tabs[2]:
        df = fetch_sheet('Sheet1')
        if df.empty:
            st.info('Nenhum cadastro disponível para edição.')
        else:
            sel = st.selectbox('Selecione MEI', [f"{i} - {r['Nome da Empresa']}" for i,r in df.iterrows()], key='ed_sel')
            idx = int(sel.split(' - ')[0])
            reg = df.loc[idx]
            with st.form('edit_form'):
                ne = st.text_input('Nome da Empresa', value=reg['Nome da Empresa'], key='ed_ne')
                nr = st.text_input('Nome do Responsável', value=reg['Nome do Responsável'], key='ed_nr')
                tel = st.text_input('Telefone', value=reg['Telefone'], key='ed_tel')
                em = st.text_input('Email', value=reg['Email'], key='ed_em')
                sg = st.text_input('Senha Gov.br', value=reg['Senha Gov.br'], key='ed_sg')
                est = st.selectbox('Estado', states, index=states.index(reg['Estado']), key='ed_est')
                cn = st.text_input('CNPJ', value=reg['CNPJ'], key='ed_cn')
                cf = st.text_input('CPF', value=reg['CPF'], key='ed_cf')
                sm = st.selectbox('Status MEI', ['Ativo','Baixado'], index=0 if reg['Status MEI']=='Ativo' else 1, key='ed_sm')
                sb3 = st.form_submit_button('Salvar Alterações')
                if sb3:
                    authenticate_google()
                    update_sheet('Sheet1', idx, [ne,nr,tel,em,sg,est,cn,cf,sm])
                    st.success('Cadastro atualizado com sucesso!')

# Chamada principal
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if st.session_state['authenticated']:
    display_dashboard()
else:
    display_login()
