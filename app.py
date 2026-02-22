import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import datetime


st.set_page_config(page_title="Tenis Elche - Gestión de Bonos", page_icon="🎾")
USER_FILE = "users.json"
CLASS_TYPES = ["Socio", "No socio", "Alumno escuela", "Clase compartida"]

def get_service():
    try:
        info = dict(st.secrets["gcp_service_account"])
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info, scopes=scope)
        return build("sheets", "v4", credentials=creds)
    except Exception:
        st.error("⚠️ Error de configuración en las credenciales.")
        st.stop()

service = get_service()
SPREADSHEET_ID = st.secrets["spreadsheet_id"]

def load_users():
    try: 
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range="usuarios!A:D"
        ).execute()
        rows = result.get("values", [])

        users_dict = {}
        for r in rows[1:]:
            if len(r) >= 4:
                users_dict[r[0]] = {"password": r[1], "rol": r[2], "timestamp": r[3]}
        return users_dict
    except Exception as e: 
        st.error("Error interno al cargar los usuarios. Comprueba tu conexión.")
        print(f"DEBUG: {e}")
        st.stop()

def delete_users(updated_users_dict):
    values = [["Usuario", "Password", "Rol", "Timestamp"]]
    
    for username, info in updated_users_dict.items():
        values.append([
            username, 
            info["password"], 
            info["rol"], 
            info.get("timestamp", datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S"))
        ])
    
    service.spreadsheets().values().clear(
        spreadsheetId=SPREADSHEET_ID, 
        range="usuarios!A:D"
    ).execute()
    
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range="usuarios!A:D",
        valueInputOption="USER_ENTERED",
        body={"values": values}
    ).execute()

def get_all_clients(service):
    clients = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range="clientes!A:B").execute()
    return clients.get("values", [])

def find_name(service, name, column):
    all_clients = get_all_clients(service)
    for i, c in enumerate(all_clients[1:], start=2):
        if len(c) > column and c[column].lower() == name.lower(): return i

def write_cell_value(service, spreadsheetId, sheetname, row, column, value):
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheetId, range=f"{sheetname}!{column}{row}",
        valueInputOption="USER_ENTERED", body={"values": [[value]]}).execute()

def append_client(name, uses):
    next_row = len(get_all_clients(service)) + 1
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID, range=f"clientes!A{next_row}:B{next_row}",
        valueInputOption="USER_ENTERED", body={"values": [[name, uses]]}).execute()

def append_class(name, monitor, class_type):
    classes = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range="clases!A:A").execute().get("values", [])
    next_row = len(classes) + 1
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID, range=f"clases!A{next_row}:D{next_row}",
        valueInputOption="USER_ENTERED", 
        body={"values": [[name, monitor, class_type, datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")]]}).execute()

def append_user(name, password, role):
    users = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range="usuarios!A:B").execute().get("values", [])
    next_row = len(users) + 1
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID, range=f"usuarios!A{next_row}:D{next_row}",
        valueInputOption="USER_ENTERED", 
        body={"values": [[name, password, role, datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")]]}).execute()

# --- GESTIÓN DE SESIÓN ---
if "user_data" not in st.session_state:
    st.session_state["user_data"] = None
if "msg" not in st.session_state:
    st.session_state["msg"] = None

def login():
    st.sidebar.title("Iniciar Sesión")
    user_input = st.sidebar.text_input("Usuario:")
    pass_input = st.sidebar.text_input("Contraseña:", type="password")
    if st.sidebar.button("Entrar"):
        users = load_users()
        if user_input in users and users[user_input]["password"] == pass_input:
            st.session_state["user_data"] = {"username": user_input, "rol": users[user_input]["rol"]}
            st.rerun()
        else:
            st.sidebar.error("Credenciales incorrectas")

try:
    if not st.session_state["user_data"]:
        login()
        st.info("Introduce tus credenciales para continuar.")
        st.stop()

    current_user = st.session_state["user_data"]["username"]
    rol = st.session_state["user_data"]["rol"]

    # --- SIDEBAR ---
    st.sidebar.subheader(f"Bienvenido, {current_user}")
    st.sidebar.caption(f"Rol: {rol}")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state["user_data"] = None
        st.rerun()

    with st.spinner('Actualizando conexión con Google Sheets...'):
        users = load_users()

    # --- LÓGICA DE RECARGA ---
    def modulo_recarga():
        st.header("Crear o Recargar Bono")
        name = st.text_input("Nombre completo del Cliente").strip()
        existe = False
        if name:
            row = find_name(service, name, column=0)
            if row:
                st.info(f"Cliente encontrado en la base de datos.", icon="✅")
                existe = True
            else:
                st.warning("Cliente no registrado. Se creará una ficha nueva al confirmar.", icon="👤")

        to_add = st.number_input("Usos a añadir", min_value=1, step=1, value=10)
        
        btn_label = "Confirmar Recarga" if existe else "Crear Cliente y Añadir Bonos"
        
        if st.button(btn_label):
            if name:
                row = find_name(service, name, column=0)
                if row:
                    res = service.spreadsheets().values().get(
                        spreadsheetId=SPREADSHEET_ID, range=f"clientes!B{row}"
                    ).execute()
                    cell_data = res.get("values", [])
                    if cell_data:
                        new_total = int(cell_data[0][0]) + to_add
                        write_cell_value(service, SPREADSHEET_ID, "clientes", row, "B", new_total)
                        st.success(f"¡Hecho! {name} ahora tiene {new_total} usos.")
                else:
                    append_client(name, to_add)
                    st.success(f"Cliente nuevo: {name} creado con {to_add} usos.")
            else:
                st.error("Introduce un nombre válido.")

    # --- ENRUTAMIENTO POR ROL ---
    if rol == "Gerente":
        st.title("Panel de administrador")
        tab1, tab2 = st.tabs(["Gestión de Bonos", "Administrar Usuarios"])
        
        with tab1:
            modulo_recarga()
        
        with tab2:
            st.header("Panel de Usuarios")
            
            if st.session_state["msg"]:
                st.info(st.session_state["msg"], icon="ℹ️")
                st.session_state["msg"] = None
                
            users = load_users()
            
            col1, col2 = st.columns(2)
            with col1:
                with st.expander("Nuevo Usuario"):
                    nu = st.text_input("Usuario").strip()
                    np = st.text_input("Contraseña", type="password")
                    nr = st.selectbox("Rol", ["Monitor", "Recepción", "Gerente"])
                    if st.button("Crear"):
                        if nu and np:
                            append_user(nu, np, nr)
                            st.session_state["msg"] = f"Usuario '{nu}' añadido correctamente."
                            st.rerun()
            
            with col2:
                with st.expander("Eliminar usuario"):
                    lista_borrar = [u for u in users.keys() if u != current_user]
                    udel = st.selectbox("Usuario a borrar", lista_borrar)
                    if st.button("Eliminar"):
                        del users[udel]
                        delete_users(users)
                        st.session_state["msg"] = f"Usuario '{udel}' eliminado del sistema."
                        st.rerun()

    elif rol == "Recepción":
        st.title("Panel de recepción")
        modulo_recarga()

    elif rol == "Monitor":
        st.title("Registro de Asistencia")
        if 'asistidos' not in st.session_state: st.session_state.asistidos = []
        
        clients = get_all_clients(service)
        if clients:
            names = [r[0] for r in clients[1:] if r]
            sel = st.selectbox("Alumno:", names)
            ct = st.selectbox("Tipo:", CLASS_TYPES)
            
            if st.button("Marcar Clase"):
                row = find_name(service, sel, column=0)
                res = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=f"clientes!B{row}").execute()
                cell = res.get("values", [])
                if cell:
                    uses = int(cell[0][0])
                    if uses <= 0: st.error("Sin bonos disponibles.")
                    else:
                        write_cell_value(service, SPREADSHEET_ID, "clientes", row, "B", uses - 1)
                        append_class(sel, current_user, ct)
                        st.session_state.asistidos.insert(0, sel)
                        st.success(f"Asistencia marcada. Quedan {uses-1} usos.")

        if st.session_state.asistidos:
            st.divider()
            for a in st.session_state.asistidos: st.write(f"✅ {a}")
            if st.button("Limpiar"):
                st.session_state.asistidos = []; st.rerun()

except Exception as e:
    st.error("Ha ocurrido un error inesperado en la aplicación. Comprueba tu conexión.")
    print(f"CRITICAL ERROR: {e}")