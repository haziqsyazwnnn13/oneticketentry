import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="ONE TICKET", layout="centered")

st.title("🎟️ ONE TICKET SYSTEM")

uploaded_file = st.file_uploader("Upload your ticket list (CSV or Excel)", type=["csv", "xlsx"])

if uploaded_file:
    # Read file (supports both CSV and Excel)
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.success(f"✅ File '{uploaded_file.name}' uploaded successfully!")
    st.write("Preview of uploaded file:")
    st.dataframe(df.head())

    # Ensure required columns exist
    if {"Name", "Matric", "ID"}.issubset(df.columns):
        # Initialize attendance list in session state
        if "attendance" not in st.session_state:
            st.session_state.attendance = pd.DataFrame(columns=df.columns)

        # Callback for marking attendance
        def mark_attendance():
            entered_value = st.session_state.entered_value.strip().lower()
            if entered_value:
                # Match by ID or Matric (case-insensitive)
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
                    else:
                        st.session_state.message = "⚠ This student is already marked present."
                else:
                    st.session_state.message = "❌ No record found with that ID or Matric."
                # Clear input after processing
                st.session_state.entered_value = ""

        # Input with Enter to submit
        st.text_input("Enter Ticket ID or Matric:", key="entered_value", on_change=mark_attendance)

        # Show feedback message
        if "message" in st.session_state:
            st.info(st.session_state.message)

        # Attendance list
        st.subheader("🧾 Current Attendance List")
        st.write(f"Total attendees: **{len(st.session_state.attendance)}**")
        st.dataframe(st.session_state.attendance.reset_index(drop=True).rename_axis("No").set_index(pd.Index(range(1, len(st.session_state.attendance) + 1))))


        # Buttons (Delete, Clear All, Download)
        if not st.session_state.attendance.empty:
            col1, col2, col3 = st.columns(3)
            with col1:
                to_delete = st.text_input("Enter ID or Matric to delete:")
                if st.button("❌ Delete Entry"):
                    st.session_state.attendance = st.session_state.attendance[
                        ~(
                            (st.session_state.attendance["ID"].astype(str).str.lower() == to_delete.lower())
                            | (st.session_state.attendance["Matric"].astype(str).str.lower() == to_delete.lower())
                        )
                    ]
                    st.info(f"Deleted {to_delete} from attendance.")
            with col2:
                if st.button("🧹 Clear All"):
                    st.session_state.attendance = pd.DataFrame(columns=df.columns)
                    st.info("Attendance list cleared.")
            with col3:
                output = BytesIO()
                st.session_state.attendance.to_excel(output, index=False)
                st.download_button(
                    "⬇ Download Excel",
                    data=output.getvalue(),
                    file_name="attendance_list.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
    else:
        st.error("The file must contain columns: Name, Matric, and ID.")
else:
    st.info("Please upload a CSV or Excel file to start.")
