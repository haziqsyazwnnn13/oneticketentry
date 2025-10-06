import streamlit as st
import pandas as pd
from io import BytesIO
import os
from pyzbar.pyzbar import decode
from PIL import Image

st.set_page_config(page_title="ONE TICKET", layout="centered")
st.title("ONE TICKET SYSTEM")

uploaded_file = st.file_uploader("Upload your ticket list (CSV or Excel)", type=["csv", "xlsx"])

# Persistent CSV file
persistent_file = "attendance_log.csv"
required_columns = ["Name", "Matric", "ID"]

# --- Load past entries safely ---
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

# --- Reload warning ---
st.warning("⚠ Any unsaved entries may be lost if you reload. Past entries in 'attendance_log.csv' are safe.")

# --- File Upload ---
if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.success(f"✅ File '{uploaded_file.name}' uploaded successfully!")
    st.dataframe(df.head())

    if set(required_columns).issubset(df.columns):

        def mark_attendance(entered_val):
            entered_value = entered_val.strip().lower()
            if entered_value:
                match = df[
                    (df["ID"].astype(str).str.lower() == entered_value)
                    | (df["Matric"].astype(str).str.lower() == entered_value)
                ]
                if not match.empty:
                    student_id = str(match.iloc[0]["ID"]).lower()
                    if not any(st.session_state.attendance["ID"].astype(str).str.lower() == student_id):
                        st.session_state.attendance = pd.concat(
                            [st.session_state.attendance, match], ignore_index=True
                        )
                        st.session_state.message = f"✅ {match.iloc[0]['Name']} marked present!"

                        if os.path.exists(persistent_file):
                            match.to_csv(persistent_file, mode='a', header=False, index=False)
                        else:
                            match.to_csv(persistent_file, mode='w', header=True, index=False)
                    else:
                        st.session_state.message = "⚠ This student is already marked present."
                else:
                    st.session_state.message = "❌ No record found with that ID or Matric."

        # --- Manual input ---
        if "entered_temp" not in st.session_state:
            st.session_state.entered_temp = ""

        def submit_manual():
            mark_attendance(st.session_state.entered_temp)
            st.session_state.entered_temp = ""

        st.text_input("Enter Ticket ID or Matric:", key="entered_temp", on_change=submit_manual)

        # --- QR Scan ---
        if "scan_active" not in st.session_state:
            st.session_state.scan_active = False

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Start Scan"):
                st.session_state.scan_active = True
        with col2:
            if st.button("Stop Scan"):
                st.session_state.scan_active = False

        if st.session_state.scan_active:
            img = st.camera_input("Scan QR Code")
            if img is not None:
                pil_img = Image.open(img)
                qr_data = decode(pil_img)
                if qr_data:
                    qr_value = qr_data[0].data.decode("utf-8")
                    if st.session_state.get("last_qr", "") != qr_value:
                        st.session_state.last_qr = qr_value
                        st.success(f"QR scanned: {qr_value}")
                        mark_attendance(qr_value)

        if "message" in st.session_state:
            st.info(st.session_state.message)

        st.subheader("🧾 Current Attendance List")
        st.write(f"Total attendees: **{len(st.session_state.attendance)}**")
        st.dataframe(
            st.session_state.attendance.reset_index(drop=True)
            .rename_axis("No")
            .set_index(pd.Index(range(1, len(st.session_state.attendance) + 1)))
        )

        if not st.session_state.attendance.empty:
            col1, col2, col3 = st.columns(3)

            with col1:
                val = st.text_input("Enter ID or Matric to delete:")
                if st.button("❌ Delete Entry"):
                    val = val.strip().lower()
                    st.session_state.attendance = st.session_state.attendance[
                        ~(
                            (st.session_state.attendance["ID"].astype(str).str.lower() == val)
                            | (st.session_state.attendance["Matric"].astype(str).str.lower() == val)
                        )
                    ]
                    st.info(f"Deleted {val} from attendance.")

            with col2:
                if st.checkbox("⚠ Confirm Clear All?"):
                    if st.button("🧹 Clear All"):
                        st.session_state.attendance = pd.DataFrame(columns=df.columns)
                        st.info("Attendance list cleared.")

            with col3:
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
        st.error("The file must contain columns: Name, Matric, and ID.")
else:
    st.info("Please upload a CSV or Excel file to start.")
