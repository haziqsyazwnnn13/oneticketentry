import streamlit as st
import pandas as pd
from io import BytesIO
import os
import time
import cv2
import numpy as np
from PIL import Image

st.set_page_config(page_title="ONE TICKET", layout="centered")
st.title("ONE TICKET SYSTEM")

uploaded_file = st.file_uploader("Upload your ticket list (CSV or Excel)", type=["csv", "xlsx"])

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

# --- File uploaded? ---
if uploaded_file:
    df = pd.read_csv(uploaded_file) if uploaded_file.name.lower().endswith(".csv") else pd.read_excel(uploaded_file)
    st.success(f"✅ File '{uploaded_file.name}' uploaded successfully!")
    st.dataframe(df.head())

    if not set(required_columns).issubset(df.columns):
        st.error("The uploaded file must contain columns: Name, Matric, and ID.")
    else:
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

        # -- Clear All --
        with col_clear:
            clear_confirm = st.checkbox("⚠ Confirm Clear All?", key="clear_confirm_checkbox")
            if st.button("🧹 Clear All") and clear_confirm:
                st.session_state.attendance = pd.DataFrame(columns=df.columns)
                pd.DataFrame(columns=required_columns).to_csv(persistent_file, index=False)
                st.success("Attendance list cleared.")

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

else:
    st.info("Please upload a CSV or Excel file to start.")
