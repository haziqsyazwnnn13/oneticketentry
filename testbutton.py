import streamlit as st
import pandas as pd
import io
from io import BytesIO
import os
import time 
import cv2
import numpy as np
from PIL import Image
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from supabase import create_client,Client
from contextlib import contextmanager


url = "https://qevcugdmkabvactukacz.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFldmN1Z2Rta2FidmFjdHVrYWN6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjA0OTExNzIsImV4cCI6MjA3NjA2NzE3Mn0.m0PXUby0T9VWY7kqLTQeprWPbJVEyWWoY-1bplcJQVY"
supabase: Client = create_client(url,key)

#database logic=================================================================================================================
# --- SUPABASE FUNCTIONS ---

def load_main_list(main_table_name: str):
    """Load main ticket list from Supabase"""
    try:
        res = supabase.table(main_table_name).select("*").execute()
        if res.data:
            return pd.DataFrame(res.data)
        else:
            st.warning(f"No data found in '{main_table_name}'.")
            return pd.DataFrame(columns=["Name", "Matric", "ID"])
    except Exception as e:
        st.error(f"❌ Failed to load from '{main_table_name}': {e}")
        return pd.DataFrame(columns=["Name", "Matric", "ID"])


def load_attendance(att_table_name: str):
    """Load attendance list from Supabase"""
    try:
        res = supabase.table(att_table_name).select("*").execute()
        if res.data:
            return pd.DataFrame(res.data)
        else:
            msg = st.empty()
            msg.warning(f"No data found in '{att_table_name}'.")
            time.sleep(2)
            msg.empty()
            return pd.DataFrame(columns=["Name", "Matric", "ID"])
    except Exception as e:
        st.error(f"❌ Failed to load from '{att_table_name}': {e}")
        return pd.DataFrame(columns=["Name", "Matric", "ID"])


def delete_attendance(att_table_name: str, student_id: str):
    """Delete one record"""
    try:
        supabase.table(att_table_name).delete().eq("ID", student_id).execute()
        st.success(f"🗑 Deleted record from '{att_table_name}'.")
        st.session_state["msg_time"] = time.time()
    except Exception as e:
        st.error(f"❌ Failed to delete from '{att_table_name}': {e}")


def clear_attendance(att_table_name: str):
    """Clear all records"""
    try:
        supabase.table(att_table_name).delete().execute()
        st.success(f"🧹 Cleared all attendance in '{att_table_name}'.")
        st.session_state["msg_time"] = time.time()
    except Exception as e:
        st.error(f"❌ Failed to clear '{att_table_name}': {e}")


def decode_qr_from_image(image: Image.Image) -> str:
    """Decode QR code from image"""
    arr = np.array(image.convert("RGB"))
    detector = cv2.QRCodeDetector()
    data, _, _ = detector.detectAndDecode(arr)
    return data or ""

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

def colored_subheader(title, color="#1A1E27"):
    st.markdown(
        f"""
        <div style="
            background-color: {color};
            padding: 10px 20px;
            border-radius: 8px;
            margin-top: 10px;
            margin-bottom: 20px;
            width: 100%;
        ">
            <h3 style="color: #FFFFFF; margin: 0;">{title}</h3>
        </div>
        """,
        unsafe_allow_html=True
    )

@contextmanager
def bgkc(color="#212B33", padding="1.5em", radius="0.5em", margin="0px"):
    """
    Creates a full-width background section that visually wraps Streamlit widgets.
    """
    container = st.container()
    with container:
        st.markdown(
            f"""
            <style>
            div[data-testid="stVerticalBlock"] > div:nth-child(1) {{
                background-color: {color};
                padding: {padding};
                border-radius: {radius};
                margin: {margin};
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
        yield container

def Overview(main_table_name, attendance_table_name):
    main_df = load_main_list(main_table_name)
    att_df = load_attendance(attendance_table_name)
    st.subheader("Main Ticket List")
    if not main_df.empty:
        main_df.index = range(1, len(main_df) + 1)
        st.dataframe(main_df, use_container_width=True, height=len(main_df) * 35 + 50)


def Record(main_table_name, attendance_table_name):
        main_df = load_main_list(main_table_name)
        att_df = load_attendance(attendance_table_name)
        st.subheader("Rock Indie")

        # --- Start / Stop QR Scan Mode ---
        if "qr_scan_mode" not in st.session_state:
            st.session_state.qr_scan_mode = False

        col1, col2 = st.columns(2)
        with col1:
            if st.button("▶ Start QR Scan"):
                st.session_state.qr_scan_mode = True
                st.session_state.active_tab = "Record"
                
        with col2:
            if st.button("🛑 Stop QR Scan"):
                st.session_state.qr_scan_mode = False
                st.session_state.active_tab = "Record"

        # === QR Camera Scanner ===
        if st.session_state.qr_scan_mode:
            img = st.camera_input("Show QR code to camera")
            
            if img:
                qr_value = decode_qr_from_image(Image.open(img))
               
                if qr_value:
                    match = main_df[
                        (main_df["ID"].astype(str) == qr_value)
                        | (main_df["Matric"].astype(str) == qr_value)
                    ]
                    
                        
                    if not match.empty:
                        student = match.iloc[0]
                        # --- Check duplicate before inserting ---
                        check = supabase.table(attendance_table_name).select("*").eq("ID", student["ID"]).execute()
                        if not check.data:
                            new_row = {
                                "Name": student["Name"],
                                "Matric": student["Matric"],
                                "ID": student["ID"]
                            }
                            supabase.table(attendance_table_name).insert(new_row).execute()
                            st.success(f"{student['Name']} marked present!")
                           
                        else:
                            st.warning("⚠ Already marked present.")
                            
                    else:
                        st.error("ID not found in main list.")
                       
                else:
                    st.info("No QR detected.")
                   
       
           
        # === Manual Entry Section ===
        st.markdown("### Manual Entry")

        if "manual_value" not in st.session_state:
            st.session_state.manual_value = ""

       # --- Manual Entry Section ---
        msg_placeholder = st.empty()  # placeholder for messages

        def process_manual_entry():
            entered_val = st.session_state.manual_value.strip()
            if not entered_val:
                return
            match = main_df[
                (main_df["ID"].astype(str) == entered_val)
                | (main_df["Matric"].astype(str) == entered_val)
            ]

            if not match.empty:
                student = match.iloc[0]
                check = supabase.table(attendance_table_name).select("*").eq("ID", student["ID"]).execute()
                if not check.data:
                    new_row = {
                        "Name": student["Name"],
                        "Matric": student["Matric"],
                        "ID": student["ID"]
                    }
                    supabase.table(attendance_table_name).insert(new_row).execute()
                    msg_placeholder.success(f"{student['Name']} marked present!")
                else:
                    msg_placeholder.warning("⚠ Already marked present.")
            else:
                msg_placeholder.error("No record found with that Matric or ID.")

            # --- Clear input box ---
            st.session_state.manual_value = ""

            # --- Auto clear message after 2 seconds ---
            time.sleep(2)
            msg_placeholder.empty()


        st.text_input(
            "Enter Ticket ID or Matric:",
            key="manual_value",
            on_change=process_manual_entry
        )
        st.button("Enter", on_click=process_manual_entry)


        # === Attendance List Display ===
        st.subheader("Attendance List")
        if not att_df.empty:
            att_df.index = range(1, len(att_df) + 1)
            st.dataframe(att_df, use_container_width=True,)
        
        else:
            st.info("No attendance recorded yet.")


def Manage(main_table_name, attendance_table_name):
        main_df = load_main_list(main_table_name)
        att_df = load_attendance(attendance_table_name)
       

        tab_main, tab_att = st.tabs(["🧾 Main List", "📋 Attendance"])

        # ------------------------------
        # MAIN LIST TAB
        # ------------------------------
        with tab_main:
            st.write("Manage Main Ticket List")
            st.dataframe(main_df, use_container_width=True)

            # --- Edit/Delete existing record ---
            with st.form("edit_delete_main"):
                lookup = st.text_input("Enter Matric or ID to Edit/Delete", key="manage_lookup")
                col1, col2 = st.columns(2)
                with col1:
                    submit_edit_lookup = st.form_submit_button("🔎 Find/Edit")
                with col2:
                    submit_delete = st.form_submit_button("🗑 Delete")

            # DELETE
            if submit_delete and lookup.strip():
                try:
                    supabase.table(main_table_name).delete().or_(
                        f"ID.eq.{lookup.strip()},Matric.eq.{lookup.strip()}"
                    ).execute()
                    st.success(f"Deleted record: {lookup.strip()}")
                    st.session_state.manage_lookup = ""
                    
                except Exception as e:
                    st.error(f"Failed to delete: {e}")

            # EDIT
            if submit_edit_lookup and lookup.strip():
                match = main_df[
                    (main_df["ID"].astype(str) == lookup.strip())
                    | (main_df["Matric"].astype(str) == lookup.strip())
                ]
                if match.empty:
                    st.error("No record found to edit.")
                    st.session_state.manage_lookup = ""
                else:
                    student = match.iloc[0].to_dict()
                    with st.form("edit_main_form"):
                        edit_name = st.text_input("Edit Name", value=student["Name"], key="edit_name")
                        edit_matric = st.text_input("Edit Matric", value=student["Matric"], key="edit_matric")
                        submit_edit = st.form_submit_button("💾 Save Changes")
                        if submit_edit:
                            updates = {}
                            if edit_name.strip() != student["Name"]:
                                updates["Name"] = edit_name.strip()
                            if edit_matric.strip() != student["Matric"]:
                                updates["Matric"] = edit_matric.strip()
                            if updates:
                                try:
                                    supabase.table(main_table_name).update(updates).or_(
                                        f"ID.eq.{student['ID']},Matric.eq.{student['Matric']}"
                                    ).execute()
                                    st.success(f"✅ Updated {edit_name.strip()}")
                                    st.session_state.manage_lookup = ""
                                    
                                except Exception as e:
                                    st.error(f"Failed to update: {e}")
                            else:
                                st.info("No changes detected.")

        # ------------------------------
        # ATTENDANCE TAB
        # ------------------------------
        with tab_att:
            st.write("Manage Attendance")
            if not att_df.empty:
                st.dataframe(att_df, use_container_width=True)
            else:
                st.info("No attendance records yet.")

            # Delete individual attendance
            with st.form("delete_att_form"):
                delete_id = st.text_input("Enter ID or Matric to Delete", key="delete_att_input")
                submit_delete_att = st.form_submit_button("🗑 Delete")
                if submit_delete_att and delete_id.strip():
                    try:
                        supabase.table(attendance_table_name).delete().or_(
                            f"ID.eq.{delete_id.strip()},Matric.eq.{delete_id.strip()}"
                        ).execute()
                        st.success(f"Deleted {delete_id.strip()}")

                        # Instead of assigning st.session_state.delete_att_input, just rerun
                        
                    except Exception as e:
                        st.error(f"Failed to delete: {e}")

            # Clear all attendance with confirmation
            with st.expander("Clear All Attendance"):
                with st.form("clear_att_form"):
                    confirm = st.text_input("Type CLEAR to confirm:")
                    submit_clear_all = st.form_submit_button("ⓘ  Clear All Attendance")

                    if submit_clear_all:
                        if confirm.strip().upper() == "CLEAR":
                            try:
                                # Supabase requires a WHERE clause — use neq (not equal) to match all rows
                                supabase.table(attendance_table_name).delete().neq("ID", "0").execute()
                                st.success("✅ All attendance cleared!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Failed to clear attendance: {e}")
                        else:
                            st.warning("⚠ Please type CLEAR to confirm.")


            with st.expander("📥 Download Attendance List"):
                if not att_df.empty:
                    output = io.BytesIO()
                    att_df.to_excel(output, index=False)
                    output.seek(0)
                    st.download_button(
                        label="⬇ Download Excel",
                        data=output,
                        file_name=f"{attendance_table_name}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.info("No attendance records to download.")

def login():
    PIN = "1234"  # change this

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔒 - LOGIN")
        st.subheader("Rock Indie")

        def check_password():
            if st.session_state.password_input == PIN:
                st.session_state.authenticated = True
                msg = st.empty()
                msg.success("ꗃ Access granted ")
                time.sleep(1.5)
                msg.empty()
            
            else:
                st.error("⚠︎ Incorrect password. Please try again.")

        st.text_input("Enter access code:", type="password", key="password_input", on_change=check_password)
        if st.button("Login"):
            check_password()
        st.stop()  # Prevent rest of app from loading until login
#Homepage==================================================================================================================================



st.set_page_config(page_title="ONETICKET - Rock Indie ", layout="centered")

col1, col2, col3 = st.columns([1, 2, 1])
    with col2: 
        st.header("ONE TICKET")
st.image("d1.png",width=1500)


def sidebar():

    page = st.sidebar.radio("Go to:", ["Overview", "Record", "Manage","FAQ", "Contact"])
    
    if page == "Overview":
        colored_subheader("Overview")
        Overview("Main_RockIndie", "Att_RockIndie")
    
    elif page == "Record":
        colored_subheader("Record Attendance")
        Record("Main_RockIndie", "Att_RockIndie")

    elif page == "Manage":
        colored_subheader("⚙ Manage Data")
        Manage("Main_RockIndie", "Att_RockIndie")        

    elif page == "FAQ":
        colored_subheader("❓ Frequently Asked Questions (FAQ)")

        with st.expander("What is the ONE TICKET Entry System?"):
            st.write("It’s a digital check-in system that helps event organizers manage ticket automation, scanning, attendance tracking, and entry validation efficiently using QR codes or uploaded ticket lists.")

        with st.expander("How do I upload my event’s ticket list?"):
            st.write("On the home page, choose **'Upload New File'** and select your ticket list in `.csv` or `.xlsx` format. The system will automatically detect and display the data for preview.")

        with st.expander("Can I use a default ticket file instead of uploading?"):
            st.write("Yes! If you already have a default file saved (e.g., `ENTRY.xlsx`), the system will automatically load it when you choose **'Use Default File'**.")

        with st.expander(" What file format does the system support?"):
            st.write("The system supports both **CSV (.csv)** and **Excel (.xlsx)** formats.")

        with st.expander("Is there a password for each event?"):
            st.write("Yes. Each event has its own unique password to ensure only authorized personnel can access its data.")

        with st.expander("Can I switch between multiple events from the same app?"):
            st.write("Yes, the homepage provides a simple selection menu. Each event has its own configuration and password protection for secure access.")

        with st.expander("How is attendance recorded?"):
            st.write("Once a participant’s ticket (or ID) is scanned or entered, their entry is logged in the attendance list automatically — preventing duplicate entries.")

        with st.expander("What happens if I upload the wrong file?"):
            st.write("Simply go back to the selection menu, reselect **'Upload New File'**, and upload the correct file. The system will refresh automatically.")

        with st.expander("Can I use this system offline?"):
            st.write("Partially. The app must run on an internet-enabled device, but local Excel/CSV file reading and writing can work without constant internet once started.")

        with st.expander("How do I register an Event"):
            st.write("You can submit the \"Event Form\" to create your own event. You will receive the bill once submited and further instruction will be sent via email.")

        with st.expander("Other Question?"):
            question = st.text_input("Feel Free to ask",help="or you can email directly at oneticket_612@gmail.com")

        data = pd.DataFrame([{
                "Question:": question
            }])
        st.dataframe(data)
        data.to_csv("Question.csv", mode="a", header=False, index=False)



    elif page == "Contact":
        colored_subheader("Email - oneticket.612@gmail.com")

    elif page =="Event Form":
        st.title("Create your event!")
        st.markdown("Please fill the form correctly")

    # --- Form Section ---
        with st.form("custom_form"):
            st.write("Fill in the details below:")
            
            # Example form fields (you can rename or remove easily)
            name = st.text_input("Full Name",help="ALL CAPITAL")
            matric = st.text_input("Matric",help="e.g:232542")
            email = st.text_input("Email Address:")
            event = st.text_input("Event Name",help="All Capital")
            status = st.selectbox("Select your status", ["Student","Staff","Others"])
            agree = st.checkbox("I confirm the above information is correct.")
            
            # Submit button
            submitted = st.form_submit_button("Submit")

        # --- Form Logic ---
        if submitted:
            if not agree:
                st.error("⚠️ Please confirm your information before submitting.")
            elif name and matric:
                # Save or display result
                st.success(f"✅ Thank you, {name}! Your form has been submitted successfully.")
                
                # Optional: Save to DataFrame (could later export to Excel)
                form_data = pd.DataFrame([{
                    "Name": name,
                    "Matric": matric,
                    "Email": email,
                    "Event": event,
                    "Status": status
                }])
                
                st.dataframe(form_data)
                
                # Optionally save to CSV
                form_data.to_csv("form_responses.csv", mode="a", header=False, index=False)
            else:
                st.warning("Please fill in all required fields.")


 


        

login()
sidebar()





#Footer==========================================================================================================================
st.image("d1.png",width=1500)
st.markdown(
        """
        <div style='text-align:center; color:gray; font-size:14px;'>
            © 2025 ONE TICKET | Developed by <b>hs</b><br>
            <a href="mailto:oneticket_612@gmail.com" style="color:gray; text-decoration:none;">Contact Support</a>
        </div>
        """,
        unsafe_allow_html=True
    )


    








