import streamlit as st
import pandas as pd
from io import BytesIO
import os
import time
import cv2
import numpy as np
from PIL import Image

def system(Title, password, file, csv):
    

    # Store login state per event
    auth_key = f"authenticated_{Title}"
    if auth_key not in st.session_state:
        st.session_state[auth_key] = False



    # Define your password here
    APP_PASSWORD = password  # 👈 change this to your secret code

    # Login form (Enter key or button both work)
    if not st.session_state[auth_key]:
        st.title("🔒 ONE TICKET SYSTEM - Login")
        st.title(Title)

        def check_password():
            if st.session_state.password_input == APP_PASSWORD:
                st.session_state[auth_key] = True
                st.success("Access granted ✅")
            
            else:
                st.error("❌ Incorrect password. Please try again.")

        st.text_input("Enter access code:", type="password", key="password_input", on_change=check_password)
        if st.button("Login"):
            check_password()
        st.stop()  # Prevent rest of app from loading until login


    st.set_page_config(page_title=f"ONE TICKET- {Title}", layout="centered")
    st.title("ONE TICKET SYSTEM")
    st.markdown("GALAU 3.0")

    # --- Auto-load ticket list ---
    DEFAULT_FILE_XLSX = file
    DEFAULT_FILE_CSV = "ENTRY.csv"

    df = None  # initialize variable
    
    choice = st.radio("Select file source:", ["🗁 Use Default File", "➜] Upload New File"])


 # --- AUTO LOAD DEFAULT FILE ---
    if choice == "🗁 Use Default File":
        if os.path.exists(DEFAULT_FILE_XLSX):
            df = pd.read_excel(DEFAULT_FILE_XLSX)
            st.write(f"✅ Loaded '{DEFAULT_FILE_XLSX}' automatically!")
        elif os.path.exists(DEFAULT_FILE_CSV):
            df = pd.read_csv(DEFAULT_FILE_CSV)
            st.success(f"✅ Loaded '{DEFAULT_FILE_CSV}' automatically!")
        else:
            st.warning("⚠ No default file found. You can upload one manually below.")

     # --- Manual Upload file---
    elif choice == "➜] Upload New File":
        uploaded_file = st.file_uploader("Choose your ticket list (CSV or Excel)", type=["csv", "xlsx"])
        if uploaded_file is not None:
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            st.write(f"✅ File '{uploaded_file.name}' uploaded successfully!")


    

    # --- DISPLAY FILE PREVIEW ---
    if df is not None:
        st.dataframe(df.head())
    else:
        st.error("❌ No file loaded yet.")


    # Persistent CSV file
    persistent_file = csv
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


#Homepage==================================================================================================================================

st.set_page_config(page_title="ONETICKET- Home", layout="centered")
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    st.image("logo.png",width=150)
with col2: 
    st.title("ONE TICKET")

page = st.sidebar.radio("Go to:", ["Home", "FAQ","Event Form", "Contact"])


if page == "Home":
   #Event selection=========================================================================    
    events = ["GALAU 3.0", "MAJMUK ALAM", "SPORTS DAY"]

    # Store selection in session state
    if "selected_event" not in st.session_state:
        st.session_state.selected_event = None

    # If no event chosen yet → show event menu
    if st.session_state.selected_event is None:
        st.subheader("🎟️ Choose Your Event")
        cols = st.columns(len(events))
        for i, name in enumerate(events):
            if cols[i].button(name, use_container_width=True):
                st.session_state.selected_event = name
                st.rerun()

    # If user has chosen an event → open that page
    else:
        # Back button
        if st.button("🏠︎"):
            st.session_state.selected_event = None
            st.rerun()
           

        # Run selected system
        
        if st.session_state.selected_event == "GALAU 3.0":
            system("GALAU 3.0", "1234", "ENTRY.xlsx","galau_data.csv")

        elif st.session_state.selected_event == "MAJMUK ALAM":
            system("MAJMUK ALAM", "2222", "ENTRY.xlsx","majmukalam_data.csv")

        elif st.session_state.selected_event == "SPORTS DAY":
            system("SPORTS DAY", "6666", "entrod.xlsx","sportsday_data.csv")


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


    
