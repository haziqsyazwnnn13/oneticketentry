import streamlit as st
import pandas as pd
from io import BytesIO
import os
import time
import cv2
import numpy as np
from PIL import Image

# --- Simple password gate ---
st.set_page_config(page_title="ONE TICKET", layout="centered")

# Store login state in session
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# Define your password here
APP_PASSWORD = "1234"  # 👈 change this to your secret code

# Login form (Enter key or button both work)
if not st.session_state.authenticated:
    st.title("🔒 ONE TICKET SYSTEM - Login")
    st.markdown("GALAU")

    def check_password():
        if st.session_state.password_input == APP_PASSWORD:
            st.session_state.authenticated = True
            st.success("Access granted ✅")
        
        else:
            st.error("❌ Incorrect password. Please try again.")

    st.text_input("Enter access code:", type="password", key="password_input", on_change=check_password)
    if st.button("Login"):
        check_password()
    st.stop()  # Prevent rest of app from loading until login


st.set_page_config(page_title="ONE TICKET", layout="centered")
st.title("ONE TICKET SYSTEM")
st.markdown("GALAU")

# --- Auto-load ticket list ---
DEFAULT_FILE_XLSX = "ENTRY_GALAU3.0.xlsx"
DEFAULT_FILE_CSV = "ENTRY.csv"

if os.path.exists(DEFAULT_FILE_XLSX):
    df = pd.read_excel(DEFAULT_FILE_XLSX)
    st.success(f"✅ Loaded '{DEFAULT_FILE_XLSX}' automatically!")
elif os.path.exists(DEFAULT_FILE_CSV):
    df = pd.read_csv(DEFAULT_FILE_CSV)
    st.success(f"✅ Loaded '{DEFAULT_FILE_CSV}' automatically!")
else:
    st.error("❌ No default file found! Please make sure 'ticket_list.xlsx' or 'ticket_list.csv' exists.")
    st.stop()

st.dataframe(df.head())

# Persistent CSV file
persistent_file = "attendance_log.csv"
required_columns = ["Name", "Matric", "ID"]

# --- Load previous attendance safely ---
if "attendance" not in st.session_state:
    if os.path.exists(persistent_file) and os.path.getsize(persistent_file) > 0:
        try:
            st.session_state.attendance = pd.read_csv(persistent_file)
            for col in required_columns:
                if col not in st.session_state.attendance.columns:
                    st.session_state.attendance[col] = ""
        except pd.errors.EmptyDataError:
            st.session_state.attendance = pd.DataFrame(columns=required_columns)
    else:
        st.session_state.attendance = pd.DataFrame(columns=required_columns)

# --- QR Decode using OpenCV (no zbar needed) ---
def decode_qr_from_image(image: Image.Image) -> str:
    arr = np.array(image.convert("RGB"))
    detector = cv2.QRCodeDetector()
    data, _, _ = detector.detectAndDecode(arr)
    return data or ""

# --- Handle query params safely ---
params = st.query_params  # new API replacing experimental_get_query_params

# --- Function to mark attendance ---
def mark_attendance(entered_val: str):
    entered_value = str(entered_val).strip().lower()
    if not entered_value:
        st.session_state.message = "❌ Empty input."
        return
    match = df[
        (df["ID"].astype(str).str.lower() == entered_value)
        | (df["Matric"].astype(str).str.lower() == entered_value)
    ]
    if not match.empty:
        student_id = str(match.iloc[0]["ID"]).lower()
        already = any(st.session_state.attendance["ID"].astype(str).str.lower() == student_id)
        if not already:
            st.session_state.attendance = pd.concat([st.session_state.attendance, match], ignore_index=True)
            st.session_state.message = f"✅ {match.iloc[0]['Name']} marked present!"
            # persist to CSV (append or write header)
            if os.path.exists(persistent_file):
                match.to_csv(persistent_file, mode="a", header=False, index=False)
            else:
                match.to_csv(persistent_file, mode="w", header=True, index=False)
        else:
            st.session_state.message = "⚠ This student is already marked present."
    else:
        st.session_state.message = "❌ No record found with that ID or Matric."

# --- Manual Input Section ---
st.subheader("📝 Manual Entry")
if "entered_temp" not in st.session_state:
    st.session_state.entered_temp = ""

def submit_manual():
    mark_attendance(st.session_state.entered_temp)
    st.session_state.entered_temp = ""

st.text_input("Enter Ticket ID or Matric:", key="entered_temp", on_change=submit_manual)
if "message" in st.session_state:
    st.info(st.session_state.message)

# --- Auto QR Scan section ---
st.subheader("QR Scan")

# restore last state from query params
if params.get("page") == "scan":
    st.session_state.auto_scan = True
else:
    st.session_state.auto_scan = False

col1, col2 = st.columns(2)
with col1:
    if st.button("▶ Start Auto Scan"):
        st.session_state.auto_scan = True
        st.session_state.last_qr = ""
        st.query_params["page"] = "scan"  # replaces experimental_set_query_params
with col2:
    if st.button("⏹ Stop Auto Scan"):
        st.session_state.auto_scan = False
        st.query_params["page"] = "home"

if st.session_state.auto_scan:
    img = st.camera_input("Show QR Code to camera")
    if img is not None:
        try:
            pil_img = Image.open(img)
            qr_value = decode_qr_from_image(pil_img)
            if qr_value:
                if st.session_state.get("last_qr", "") != qr_value:
                    st.session_state.last_qr = qr_value
                    st.success(f"QR scanned: {qr_value}")
                    mark_attendance(qr_value)
            else:
                st.info("No QR detected in the captured frame.")
        except Exception as e:
            st.error(f"Error decoding image: {e}")

        # Wait briefly before rerun
        time.sleep(1)
        st.rerun()

# --- Attendance Table + Actions ---
st.subheader("🧾 Current Attendance List")
st.write(f"Total attendees: **{len(st.session_state.attendance)}**")
if not st.session_state.attendance.empty:
    display_df = st.session_state.attendance.reset_index(drop=True)
    display_df.index = range(1, len(display_df) + 1)
    st.dataframe(display_df)
else:
    st.info("No attendees yet.")

st.write("---")
col_del, col_clear, col_dl = st.columns(3)

# -- Delete Entry --
with col_del:
    delete_val = st.text_input("Enter ID or Matric to delete:", key="delete_input")
    if st.button("❌ Delete Entry"):
        val = delete_val.strip().lower()
        if val:
            before = len(st.session_state.attendance)
            st.session_state.attendance = st.session_state.attendance[
                ~(
                    (st.session_state.attendance["ID"].astype(str).str.lower() == val)
                    | (st.session_state.attendance["Matric"].astype(str).str.lower() == val)
                )
            ].reset_index(drop=True)
            after = len(st.session_state.attendance)
            if after < before:
                st.success(f"Deleted record(s) matching '{val}'.")
                if not st.session_state.attendance.empty:
                    st.session_state.attendance.to_csv(persistent_file, index=False)
                else:
                    pd.DataFrame(columns=required_columns).to_csv(persistent_file, index=False)
            else:
                st.warning(f"No matching record found for '{val}'.")
        else:
            st.warning("Please enter a value to delete.")

# -- Clear All (auto untick) --
with col_clear:
    if "clear_confirm" not in st.session_state:
        st.session_state.clear_confirm = False

    st.session_state.clear_confirm = st.checkbox("⚠ Confirm Clear All?", value=st.session_state.clear_confirm)

    if st.button("🧹 Clear All") and st.session_state.clear_confirm:
        st.session_state.attendance = pd.DataFrame(columns=df.columns)
        pd.DataFrame(columns=required_columns).to_csv(persistent_file, index=False)
        st.success("Attendance list cleared.")
        st.session_state.clear_confirm = False  # ✅ auto reset
       # st.rerun()

        st.session_state.clear_confirm = False
        st.session_state.clear_confirm_checkbox = False  # reset checkbox widget
        st.rerun()

# -- Download --
with col_dl:
    output = BytesIO()
    st.session_state.attendance.to_excel(output, index=False)
    output.seek(0)
    st.download_button(
        "⬇ Download Excel",
        data=output,
        file_name="attendance_list.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

