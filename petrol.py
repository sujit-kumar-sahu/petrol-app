import datetime
import sqlite3
import pandas as pd
import streamlit as st

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("bike_tracker.db", check_same_thread=False)
    cursor = conn.cursor()
    
    # Members table with passwords
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    
    # Rides table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            riders TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            start_odo REAL NOT NULL,
            end_odo REAL,
            distance REAL,
            petrol_price REAL,
            total_cost REAL,
            status TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

conn = init_db()
cursor = conn.cursor()

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Petrol.py - Bike Expense Tracker", layout="wide")

# --- SESSION STATE FOR LOGIN ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

# --- LOGIN SCREEN ---
if not st.session_state.logged_in:
    st.title("⛽ Petrol.py: Login")
    st.markdown("Please log in with your member credentials to access the app.")
    
    tab_login, tab_register = st.tabs(["🔑 Login", "➕ Create Account"])
    
    with tab_login:
        login_name = st.text_input("Name", key="login_name_input")
        login_pass = st.text_input("Password", type="password", key="login_pass_input")
        if st.button("Log In"):
            cursor.execute("SELECT * FROM members WHERE name = ? AND password = ?", (login_name.strip(), login_pass.strip()))
            user = cursor.fetchone()
            if user:
                st.session_state.logged_in = True
                st.session_state.username = login_name.strip()
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Invalid Name or Password.")
                
    with tab_register:
        reg_name = st.text_input("Choose a Username", key="reg_name_input")
        reg_pass = st.text_input("Choose a Password", type="password", key="reg_pass_input")
        if st.button("Register Member"):
            if reg_name.strip() and reg_pass.strip():
                try:
                    cursor.execute("INSERT INTO members (name, password) VALUES (?, ?)", (reg_name.strip(), reg_pass.strip()))
                    conn.commit()
                    st.success("Account created! You can now log in.")
                except sqlite3.IntegrityError:
                    st.error("Username already exists!")
            else:
                st.warning("Please fill in both fields.")
                
    st.stop()

# --- MAIN APP ---
st.title(f"⛽ Petrol.py: Welcome, {st.session_state.username}!")

# --- SIDEBAR: CONTROLS & PASSWORD CHANGE ---
st.sidebar.markdown(f"**Logged in as:** `{st.session_state.username}`")
if st.sidebar.button("🚪 Log Out"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("🔒 Change Password")
old_pass = st.sidebar.text_input("Current Password", type="password", key="old_pass")
new_pass = st.sidebar.text_input("New Password", type="password", key="new_pass")
if st.sidebar.button("Update Password"):
    if old_pass and new_pass:
        cursor.execute("SELECT * FROM members WHERE name = ? AND password = ?", (st.session_state.username, old_pass))
        if cursor.fetchone():
            cursor.execute("UPDATE members SET password = ? WHERE name = ?", (new_pass, st.session_state.username))
            conn.commit()
            st.sidebar.success("Password updated successfully!")
        else:
            st.sidebar.error("Incorrect current password.")
    else:
        st.sidebar.warning("Please fill in both password fields.")

cursor.execute("SELECT name FROM members")
members = [row[0] for row in cursor.fetchall()]
st.sidebar.markdown("---")
st.sidebar.write("**All Members:**", ", ".join(members))

# --- NAVIGATION TABS ---
tab1, tab2, tab3 = st.tabs(["🚀 Start Ride", "🏁 End Ride & Calculate", "📊 Ledger & History"])

# --- TAB 1: START RIDE (With Active Ride Interception Check) ---
with tab1:
    st.header("Start a New Ride")
    
    # Check if there's any ongoing ride left unended by someone else
    cursor.execute("SELECT id, riders, start_time, start_odo FROM rides WHERE status = 'Ongoing'")
    ongoing_ride = cursor.fetchone()
    
    if ongoing_ride:
        active_id, active_riders, active_start_time, active_start_odo = ongoing_ride
        
        st.warning(f"⚠️ **Attention!** There is an active ongoing ride (ID: {active_id}) started by **{active_riders}** at `{active_start_time}` that was never ended!")
        st.info(f"Since you ({st.session_state.username}) are trying to take the bike now, you must first close out the previous ride on their behalf before starting a new one.")
        
        st.markdown("### Close Previous Ride First")
        prev_end_img = st.camera_input("Take odometer picture to close previous ride")
        prev_end_odo = st.number_input("Enter Current Odometer Reading (KM)", min_value=active_start_odo, step=0.1, key="prev_end_odo")
        petrol_price_prev = st.number_input("Today's Petrol Price (per Liter)", min_value=0.0, value=100.0, step=0.5, key="pp_prev")
        mileage_prev = st.number_input("Bike Mileage (KM per Liter)", min_value=5.0, value=45.0, step=1.0, key="m_prev")
        
        if st.button("🏁 Force End Previous Ride & Proceed"):
            if prev_end_img is None:
                st.error("Please capture the odometer picture.")
            elif prev_end_odo <= active_start_odo:
                st.error("End odometer must be greater than start odometer.")
            else:
                end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                distance = prev_end_odo - active_start_odo
                total_cost = (distance / mileage_prev) * petrol_price_prev
                
                cursor.execute("""
                    UPDATE rides 
                    SET end_time = ?, end_odo = ?, distance = ?, petrol_price = ?, total_cost = ?, status = 'Completed'
                    WHERE id = ?
                """, (end_time, prev_end_odo, distance, petrol_price_prev, total_cost, active_id))
                conn.commit()
                st.success(f"Previous ride successfully closed! Distance: {distance} KM. Now you can start your ride below.")
                st.rerun()
                
    else:
        # Normal Start Ride Flow
        selected_riders = st.multiselect("Select Rider(s)", members, default=[st.session_state.username])
        
        st.markdown("### Odometer Picture (Before Ride)")
        start_img_file = st.camera_input("Take a picture of the odometer (Start)")
        start_odo = st.number_input("Enter Odometer Reading (Start in KM)", min_value=0.0, step=0.1)
        
        if st.button("🚀 Register & Start Ride"):
            if not selected_riders:
                st.error("Please select at least one rider.")
            elif start_img_file is None:
                st.error("Please capture the start odometer picture.")
            else:
                start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                riders_str = ",".join(selected_riders)
                
                cursor.execute("""
                    INSERT INTO rides (riders, start_time, start_odo, status)
                    VALUES (?, ?, ?, ?)
                """, (riders_str, start_time, start_odo, "Ongoing"))
                conn.commit()
                st.success(f"Ride started successfully at {start_time} for: {riders_str}!")
                st.rerun()

# --- TAB 2: END RIDE ---
with tab2:
    st.header("End Active Ride")
    cursor.execute("SELECT id, riders, start_time, start_odo FROM rides WHERE status = 'Ongoing'")
    ongoing_rides = cursor.fetchall()
    
    if not ongoing_rides:
        st.info("No ongoing rides found.")
    else:
        ride_options = {f"Ride ID {r[0]} | Riders: {r[1]} | Started: {r[2]}": r for r in ongoing_rides}
        selected_ride_key = st.selectbox("Select Ongoing Ride", list(ride_options.keys()))
        chosen_ride = ride_options[selected_ride_key]
        
        ride_id, riders_str, start_time, start_odo = chosen_ride
        st.write(f"**Starting Odometer:** {start_odo} KM")
        
        st.markdown("### Odometer Picture (After Ride)")
        end_img_file = st.camera_input("Take a picture of the odometer (End)")
        end_odo = st.number_input("Enter Odometer Reading (End in KM)", min_value=start_odo, step=0.1)
        
        petrol_price = st.number_input("Today's Petrol Price (per Liter)", min_value=0.0, value=100.0, step=0.5)
        mileage = st.number_input("Bike Mileage (KM per Liter)", min_value=5.0, value=45.0, step=1.0)
        
        if st.button("🏁 Complete Ride & Calculate Split"):
            if end_img_file is None:
                st.error("Please capture the end odometer picture.")
            elif end_odo <= start_odo:
                st.error("End odometer must be greater than start odometer.")
            else:
                end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                distance = end_odo - start_odo
                total_cost = (distance / mileage) * petrol_price
                
                cursor.execute("""
                    UPDATE rides 
                    SET end_time = ?, end_odo = ?, distance = ?, petrol_price = ?, total_cost = ?, status = 'Completed'
                    WHERE id = ?
                """, (end_time, end_odo, distance, petrol_price, total_cost, ride_id))
                conn.commit()
                
                st.success(f"Ride completed! Total Distance: {distance} KM | Total Cost: ₹{total_cost:.2f}")
                riders_list = riders_str.split(",")
                share_per_person = total_cost / len(riders_list)
                st.info(f"Split among {len(riders_list)} riders: **₹{share_per_person:.2f} each**.")
                st.rerun()

# --- TAB 3: LEDGER & HISTORY ---
with tab3:
    st.header("📊 Ride History & Expense Ledger")
    cursor.execute("SELECT id, riders, start_time, end_time, distance, total_cost, status FROM rides")
    all_rides = cursor.fetchall()
    
    if all_rides:
        df_rides = pd.DataFrame(all_rides, columns=["ID", "Riders", "Start Time", "End Time", "Distance (KM)", "Total Cost (₹)", "Status"])
        st.dataframe(df_rides, use_container_width=True)
    else:
        st.info("No ride history available yet.")
        
    st.subheader("💡 Individual Balances (Who Owes What)")
    if all_rides:
        cursor.execute("SELECT riders, total_cost FROM rides WHERE status = 'Completed'")
        completed_rides = cursor.fetchall()
        
        balances = {m: 0.0 for m in members}
        for riders_str, total_cost in completed_rides:
            if total_cost:
                riders_list = riders_str.split(",")
                share = total_cost / len(riders_list)
                for rider in riders_list:
                    if rider in balances:
                        balances[rider] += share
                    
        df_balance = pd.DataFrame(list(balances.items()), columns=["Member", "Total Amount Owed (₹)"])
        st.dataframe(df_balance, use_container_width=True)
    else:
        st.write("No completed rides to calculate balances.")
