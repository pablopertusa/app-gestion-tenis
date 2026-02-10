import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import json
import datetime

def get_credentials():
    data = dict(st.secrets["gcp_service_account"])
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(data, scopes=scope)
    return creds

def get_credentials_local(filename):
    with open(filename, "r") as file:
        data = json.load(file)

    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(data, scopes=scope)
    return creds

password = st.sidebar.text_input("Contraseña de acceso:", type="password")

if password == "tenis":
    local = True
    st.title("Gestión de Bonos - Tenis Elche")
    if local:
        creds = get_credentials_local("gestion-tenis-elche-92bd1d7e8796.json")
    else:
        creds = get_credentials()

    creds = get_credentials_local("gestion-tenis-elche-92bd1d7e8796.json")
    service = build("sheets", "v4", credentials=creds)

    SPREADSHEET_ID = "1Fst1DKSFdbTTEmyrYWqrNlmu_evynOyzm2d1CwLNT5U"
    ALL_CLIENTS_RANGE_NAME = "clientes!A:B"
    ALL_CLASSES_RANGE_NAME = "clases!A:C"

    def get_all_clients(service):
        clients = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId = SPREADSHEET_ID, range=ALL_CLIENTS_RANGE_NAME)
            .execute()
        )
        rows = clients.get("values", [])
        return rows

    def get_all_classes(service):
        classes = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId = SPREADSHEET_ID, range=ALL_CLASSES_RANGE_NAME)
            .execute()
        )
        rows = classes.get("values", [])
        return rows

    def find_name(service, name, column):
        all_clients = get_all_clients(service)
        row = 2
        found = False
        for c in all_clients[1:]:
            if c[column] == name:
                found = True
                break
            else:
                row += 1
        if found:
            return row

    def read_cell_value(service, spreadsheetId, sheetname, row, column):
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId = spreadsheetId, range=f"{sheetname}!{column}{row}:{column}{row}")
            .execute()
        )
        row = result.get("values", [])
        return row

    def write_cell_value(service, spreadsheetId, sheetname, row, column, value):
        result = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId = spreadsheetId,
                range = f"{sheetname}!{column}{row}:{column}{row}",
                valueInputOption = "USER_ENTERED",
                body = {"values": [[value]]}
            )
            .execute()
        )
        return result

    def get_next_row_clients(service):
        clients = get_all_clients(service)
        return len(clients) + 1

    def get_next_row_classes(service):
        classes = get_all_classes(service)
        return len(classes) + 1

    def append_client(name, uses, service = service, spreadsheetId = SPREADSHEET_ID):
        next_row = get_next_row_clients(service)
        result = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId = spreadsheetId,
                range = f"clientes!A{next_row}:B{next_row}",
                valueInputOption = "USER_ENTERED",
                body = {"values": [[name, uses]]}
            )
            .execute()
        )
        return result

    def append_class(name, monitor, service = service, spreadsheetId = SPREADSHEET_ID):
        next_row = get_next_row_classes(service)
        result = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId = spreadsheetId,
                range = f"clases!A{next_row}:C{next_row}",
                valueInputOption = "USER_ENTERED",
                body = {"values": [[name, monitor, datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")]]}
            )
            .execute()
        )
        return result

    st.title("Gestión de Bonos - Tenis Elche")

    rol = st.sidebar.selectbox("Tu Rol:", ["Recepción", "Monitor", "Gerente"])

    # --- LÓGICA DE RECEPCIÓN ---
    if rol == "Recepción":
        st.header("Crear o Recargar Bono")
        name = st.text_input("Nombre completo del Cliente").strip()
        to_add = st.number_input("Cantidad de usos a añadir", min_value=1, step=1, value=10)
        
        if st.button("Confirmar Recarga"):
            if name:
                    row = find_name(service, name, column=0)
                    if row is not None:
                        cell_data = read_cell_value(service, SPREADSHEET_ID, "clientes", str(row), "B")
                        if cell_data != []:
                            try:
                                uses = int(cell_data[0][0])
                                new_total = uses + to_add
                                write_cell_value(service, SPREADSHEET_ID, "clientes", row, "B", new_total)
                                st.success(f"¡Actualizado! {name} ahora tiene {new_total} usos.")
                            except Exception as e:
                                st.error("Ha ocurrido un error interno. La fuente de datos puede que contenga errores.")

                    else:
                        append_client(name, to_add)
                        st.success(f"Cliente nuevo: {name} registrado con {to_add} usos.")
            else:
                st.error("Por favor, introduce un nombre.")

    # --- LÓGICA DE MONITOR ---
    elif rol == "Monitor":

        # Esto contendrá el nombre de monitor de la sesión cuando hayan cuentas
        monitor_name = "monitor_01"

        st.header("Registro de Asistencia")
        
        if 'asistidos' not in st.session_state:
            st.session_state.asistidos = []

        clients = get_all_clients(service)
        names = [r[0] for r in clients[1:]]
        
        selected = st.selectbox("Selecciona al alumno que ha venido:", names)
        
        if st.button("Marcar Asistencia"):
            row = find_name(service, selected, column=0)
            cell_data = read_cell_value(service, SPREADSHEET_ID, "clientes", str(row), "B")
            
            if cell_data != []:
                uses = cell_data[0][0]
                try:
                    uses = int(uses)
                    if uses <= 0:
                        st.error(f"❌ ¡OJO! {selected} no tiene bonos disponibles. Debe recargar.")
                    else:
                        new_total = uses - 1
                        write_cell_value(service, SPREADSHEET_ID, "clientes", row, "B", new_total)
                        append_class(selected, monitor_name)
                        
                        if selected not in st.session_state.asistidos:
                            st.session_state.asistidos.insert(0, selected)
                        
                        if new_total == 0:
                            st.warning(f"ÚLTIMO BONO. Asistencia registrada. A {selected} le quedan {new_total} usos.")
                        else:
                            st.success(f"Asistencia registrada. A {selected} le quedan {new_total} usos.")
                except Exception as e:
                    st.error(f"Error al procesar los datos: {e}")

        if st.session_state.asistidos:
            st.divider()
            st.subheader("Alumnos registrados en esta sesión:")
            for alumno in st.session_state.asistidos:
                st.write(f"✅ {alumno}")
            
            if st.button("Limpiar lista"):
                st.session_state.asistidos = []
                st.rerun()
else:
    st.warning("Por favor, introduce la contraseña en el lateral para acceder.")
