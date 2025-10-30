import streamlit as st
import pandas as pd
from io import BytesIO
import os
import time 
import cv2
import numpy as np
from PIL import Image
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from supabase import create_client,Client


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
            st.warning(f"No data found in '{att_table_name}'.")
            return pd.DataFrame(columns=["Name", "Matric", "ID"])
    except Exception as e:
        st.error(f"❌ Failed to load from '{att_table_name}': {e}")
        return pd.DataFrame(columns=["Name", "Matric", "ID"])


def add_attendance(att_table_name: str, row: dict):
    """Insert one attendance record if not duplicate"""
    try:
        check = supabase.table(att_table_name).select("*").eq("ID", row["ID"]).execute()
        if not check.data:
            supabase.table(att_table_name).insert(row).execute()
            st.success(f"✅ {row['Name']} marked present!")
            st.session_state["msg_time"] = time.time()
        else:
            st.warning("⚠ Already marked present.")
    except Exception as e:
        st.error(f"❌ Failed to add record to '{att_table_name}': {e}")


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







#Main Function==========================================================================
def system(event_name, main_table_name, attendance_table_name):
    st.title(f"🎫 {event_name} Attendance System")

    # --- Load Data ---
    main_df = load_main_list(main_table_name)
    att_df = load_attendance(attendance_table_name)

    # === Tabs ===
    tab1, tab2, tab3 = st.tabs(["📋 Overview", "🧾 Record", "⚙ Manage"])

    # TAB 1: Overview
    with tab1:
        st.subheader("Main Ticket List")
        if not main_df.empty:
            main_df.index = range(1, len(main_df) + 1)
        st.dataframe(main_df)

    # TAB 2: Record Attendance
    with tab2:
        st.subheader("Record Attendance")

        if "qr_scan_mode" not in st.session_state:
            st.session_state.qr_scan_mode = False

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📷 Start QR Scan"):
                st.session_state.qr_scan_mode = True
                st.rerun()
        with col2:
            if st.button("🛑 Stop QR Scan"):
                st.session_state.qr_scan_mode = False
                st.rerun()

        # Manual Entry
        def handle_manual_input():
            val = st.session_state.manual_entry.strip()
            if val:
                match = main_df[
                    (main_df["ID"].astype(str) == val)
                    | (main_df["Matric"].astype(str) == val)
                ]
                if not match.empty:
                    add_attendance(attendance_table_name, match.iloc[0].to_dict())
                else:
                    st.error("❌ ID not found in main list.")

        st.text_input(
            "Enter Matric or ID manually:",
            key="manual_entry",
            on_change=handle_manual_input
        )
        if st.button("✅ Submit Manual Entry"):
            handle_manual_input()

        # QR Scan
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
                        add_attendance(attendance_table_name, match.iloc[0].to_dict())
                    else:
                        st.error("❌ QR not found in main list.")
                else:
                    st.info("No QR detected.")

        st.subheader("Attendance List")
        if not att_df.empty:
            att_df.index = range(1, len(att_df) + 1)
        st.dataframe(att_df)

    # TAB 3: Manage Data
    with tab3:
        st.subheader("Manage Data")

        manage_type = st.radio("Select Table to Manage:", ["Main List", "Attendance"])

        if manage_type == "Main List":
            st.dataframe(main_df)
        else:
            st.dataframe(att_df)
            if st.button("🧹 Clear All Attendance"):
                clear_attendance(attendance_table_name)
                st.rerun()




def login(): 
            SHEET_URL = "https://docs.google.com/spreadsheets/d/1xPpPziu-iugDEvf-A79Y6qffjFK7MuCONY0haMQ-8y4/export?format=csv"

            @st.cache_data(ttl=60)
            def load_users():
                import pandas as pd
                df = pd.read_csv(SHEET_URL)
                df.columns = [c.strip().lower() for c in df.columns]
                df = df.dropna(subset=["username", "password"])
                df["username"] = df["username"].astype(str).str.strip().str.lower()
                df["password"] = df["password"].astype(str).str.strip()
                return dict(zip(df["username"], df["password"]))

            USERS = load_users()

            # ========================
            # LOGIN LOGIC
            # ========================

            # If no user is logged in → show login form
            if "logged_user" not in st.session_state:
                st.title("🔒 ONE TICKET SYSTEM - Login")

                def check_login():
                    user_key = st.session_state.username_input.strip().lower()
                    pw = st.session_state.password_input.strip()

                    if user_key in USERS and pw == USERS[user_key]:
                        st.session_state["logged_user"] = user_key
                        msg = st.empty()
                        msg.success("✅ Access granted — redirecting...")
                        time.sleep(1.5)
                        msg.empty()
                        
                    
                    else:
                        st.error("⚠ Invalid username or password.")
                        st.session_state.username_input = ""
                        st.session_state.password_input = ""

                st.text_input("Username:", key="username_input")
                st.text_input("Password:", type="password", key="password_input", on_change=check_login)
                if st.button("Login"):
                    check_login()
                st.stop()

            # ========================
            # AFTER LOGIN SUCCESS
            # ========================
            username = st.session_state["logged_user"]
            

            # ✅ Redirect immediately to the matching system
            
            # ========================
            # LOGOUT BUTTON
            # ========================
            if st.button("🔒 Logout"):
                for key in ["logged_user", "username_input", "password_input"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
            
                

            return username










#Homepage==================================================================================================================================

st.set_page_config(page_title="ONETICKET- Login", layout="centered")
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    st.image("logo.png",width=150)
with col2: 
    st.title("ONE TICKET")

def sidebar():

    page = st.sidebar.radio("Go to:", ["Login", "FAQ", "Event Form", "Contact"])
    Title = "Welcome"



    if page == "Login":
        
        username = login()
        if username == "irfancemboi":
                system(
                        "ROCK INIDIE", "Main_RockIndie","Att_RockIndie"
                    )
        elif username == "3101":
            system("TEATER MALAM")




        

    elif page == "FAQ":
        st.header("❓ Frequently Asked Questions (FAQ)")

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
        st.write("Email - oneticket_612@gmail.com")

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


    