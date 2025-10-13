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


# ================= GOOGLE SHEET SETUP ==================
service_account_info = st.secrets["gcp_service_account"]

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
sheets_service = build("sheets", "v4", credentials=creds)

# --- Helper Functions ---
# Helper: write a DataFrame to a sheet (header + rows)
def write_df_to_sheet(sheet_id, df, sheet_range="Sheet1!A1"):
    """
    Overwrite the sheet range starting at A1 with the df (header + rows).
    Converts all values to strings (Google API expects JSON-safe types).
    """
    # Ensure header is present
    header = list(df.columns)
    rows = df.astype(str).values.tolist() if not df.empty else []
    values = [header] + rows
    sheets_service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=sheet_range,
        valueInputOption="RAW",
        body={"values": values}
    ).execute()


# Helper: refresh local attendance cache from the sheet
def refresh_attendance_from_sheet(sheet_id, required_columns=["Name","Matric","ID"]):
    try:
        df_att = read_sheet(sheet_id, range_name="Sheet1!A:C")
        # normalize columns: ensure required_columns exist
        for col in required_columns:
            if col not in df_att.columns:
                df_att[col] = ""
        # reorder to required columns if other columns exist
        df_att = df_att.loc[:, [c for c in required_columns if c in df_att.columns] + 
                            [c for c in df_att.columns if c not in required_columns]]
        st.session_state.attendance = df_att.reset_index(drop=True)
    except Exception:
        st.session_state.attendance = pd.DataFrame(columns=required_columns)

def read_sheet(sheet_id, range_name="Sheet1!A:C"):
    """Read data from Google Sheet and return DataFrame"""
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=range_name
    ).execute()
    values = result.get("values", [])
    if not values:
        return pd.DataFrame(columns=["Name", "Matric", "ID"])
    headers = values[0]
    rows = values[1:]
    df = pd.DataFrame(rows, columns=headers)
    return df

def append_to_sheet(sheet_id, row_data):
    """Append a row to the attendance sheet"""
    sheets_service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range="Sheet1!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row_data]},
    ).execute()

def clear_sheet(sheet_id):
    """Clear all data from attendance sheet except header"""
    sheets_service.spreadsheets().values().clear(
        spreadsheetId=sheet_id, range="Sheet1!A2:Z"
    ).execute()
# ==========================================================


#Main Function==========================================================================
def system(Title, mainId, attId):
    
    st.set_page_config(page_title=f"ONE TICKET- {Title}", layout="centered")
    st.title(Title)
    
    tabs = st.tabs(["Overview ", "Entry", "Record", "⚙ Settings"])

    with tabs[0]:#=============================================Overview=======================================================
        msg_placeholder = st.empty()
        msg_placeholder.info("ⴵ Loading data")
        time.sleep(2)

        MAIN_SHEET_ID = mainId
        ATTENDANCE_SHEET_ID = attId

        # ---- session-state initialization ----
        if "attendance" not in st.session_state:
            # load from sheet if possible
            try:
                refresh_attendance_from_sheet(ATTENDANCE_SHEET_ID, required_columns=["Name","Matric","ID"])
                #msg_placeholder = st.empty()
                msg_placeholder.success("ⴵ Load data from last session")
                time.sleep(2)
            except Exception as e:
                st.warning(f"⚠ Could not load attendance from sheet: {e}")
                st.session_state.attendance = pd.DataFrame(columns=["Name","Matric","ID"])

        # Booleans / user-controls used later
        if "clear_confirm" not in st.session_state:
            st.session_state.clear_confirm = False

        # Ensure delete_input key exists (text_input will create it too; this avoids attribute errors)
        if "delete_input" not in st.session_state:
            st.session_state.delete_input = ""


        try:
            df = read_sheet(MAIN_SHEET_ID)
            msg_placeholder.success(f"ⴵ Load main list from {Title} record")
            time.sleep(2)
            msg_placeholder.empty()
           # st.dataframe(df.head())
            df_display = df.reset_index(drop=True)
            df_display.index = df_display.index + 1  # Start index from 1
            st.dataframe(df_display, use_container_width=True)


        except Exception as e:
            st.error(f"⚠ Failed to load main sheet: {e}")
            st.stop()

        

        # --- Google Sheet Attendance (Live persistence) ---

        
        required_columns = ["Name", "Matric", "ID"]

    

        # --- QR Decode using OpenCV (no zbar needed) ---
    def decode_qr_from_image(image: Image.Image) -> str:
        arr = np.array(image.convert("RGB"))
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(arr)
        return data or ""

        # --- Handle query params safely ---
        params = st.query_params  # new API replacing experimental_get_query_params

    with tabs[1]:#==========================================================Entry===============================================
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
                    new_row = match.iloc[0].tolist()
                    # Append to Google Sheet
                    append_to_sheet(ATTENDANCE_SHEET_ID, new_row)

                    # Update local session cache
                    st.session_state.attendance = pd.concat(
                        [st.session_state.attendance, match], ignore_index=True
                    )
                    st.session_state.message = f"✅ {match.iloc[0]['Name']} marked present!"
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
        st.subheader("📷 QR Scan")

        if "auto_scan" not in st.session_state:
            st.session_state.auto_scan = False

        col1, col2 = st.columns(2)
        with col1:
            if st.button("▶ Start Auto Scan"):
                st.session_state.auto_scan = True
        with col2:
            if st.button("⏹ Stop Auto Scan"):
                st.session_state.auto_scan = False

        if st.session_state.auto_scan:
            img = st.camera_input("Show QR Code to camera")
            if img is not None:
                try:
                    pil_img = Image.open(img)
                    qr_value = decode_qr_from_image(pil_img)
                    if qr_value:
                        if st.session_state.get("last_qr") != qr_value:
                            st.session_state.last_qr = qr_value
                            st.success(f"QR scanned: {qr_value}")
                            mark_attendance(qr_value)
                            time.sleep(2)  # let user see the success message
                            st.balloons()
                            st.rerun()     # rerun to refresh attendance list
                    else:
                        st.info("No QR detected — try again.")
                except Exception as e:
                    st.error(f"Error decoding QR: {e}")


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

        
        
   
        

    with tabs[2]:#================================================Record=================================================
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

        
        
        # -- Delete Entry (Google Sheet compatible) --===========================================
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
                        st.success(f"✅ Deleted record(s) matching '{val}'. Updating sheet...")
                        try:
                            # ✅ Rewrite entire sheet cleanly without duplication
                            clear_sheet(ATTENDANCE_SHEET_ID)
                            for _, row in st.session_state.attendance.iterrows():
                                append_to_sheet(ATTENDANCE_SHEET_ID, row.tolist())
                            st.info("updated successfully.")
                            time.sleep(2)
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Failed to update Google Sheet: {e}")
                    else:
                        st.warning(f"No matching record found for '{val}'.")
                else:
                    st.warning("Please enter a value to delete.")


        # -- Clear All (auto untick) --
        # -- Clear All (Google Sheet integrated) --
        with col_clear:
            if "clear_confirm" not in st.session_state:
                st.session_state.clear_confirm = False

            st.session_state.clear_confirm = st.checkbox("⚠ Confirm Clear All?", value=st.session_state.clear_confirm)

            if st.button("🧹 Clear All") and st.session_state.clear_confirm:
                try:
                    clear_sheet(ATTENDANCE_SHEET_ID)  # ✅ Clears all rows except header in Google Sheet
                    st.session_state.attendance = pd.DataFrame(columns=required_columns)
                    st.success("✅ Attendance sheet cleared successfully.")
                    time.sleep(2)
                    st.session_state.clear_confirm = False
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to clear sheet: {e}")




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
                        "ROCK INDIE",
                        "1jMMZawgQwm3Fgmyqk8zEsgDY0ekzuBBMxWIOA9b6mZI",
                        "1h9Whs_042649-FHqZzb-TkXFksZTdlPw1RPZilSgJaI"
                    )




        

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


    