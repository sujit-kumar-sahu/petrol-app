import datetime
import sqlite3
import pandas as pd
import streamlit as st

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("bike_tracker.db", check_same_thread=False)
    cursor = conn.cursor()
    
    # Members table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
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

# Fetch existing members for verification
cursor.execute("SELECT name FROM members")
members = [row[0] for row in cursor.fetchall()]

# --- LOGIN SCREEN ---
if not st.session_state.logged_in:
    st.title("⛽ Petrol.py: Login")
    st.markdown("Type your exact username to log in, or register a new member below.")
    
    tab_login, tab_register = st.tabs(["🔑 Log In", "➕ Register Member"])
    
    with tab_login:
        login_name_input = st.text_input("Enter Your Username", key="login_text_input")
        if st.button("Log In"):
            entered_name = login_name_input.strip()
            # Check if name exists in database (case-insensitive check can also be applied if needed)
            cursor.execute("SELECT name FROM members WHERE name = ?", (entered_name,))
            user_exists = cursor.fetchone()
            
            if entered_name and user_exists:
                st.session_state.logged_in = True
                st.session_state.username = entered_name
                st.success(f"Welcome back, {entered_name}!")
                st.rerun()
            elif not entered_name:
                st.warning("Please enter a username.")
            else:
                st.error("Username not found! Please check the spelling or register first.")
                
    with tab_register:
        reg_name = st.text_input("Enter New Member Name", key="reg_name_input")
        if st.button("Register Member"):
            if reg_name.strip():
                try:
                    cursor.execute("INSERT INTO members (name) VALUES (?)", (reg_name.strip(),))
                    conn.commit()
                    st.success(f"Member '{reg_name.strip()}' created successfully! You can now switch to the Log In tab.")
                except sqlite3.IntegrityError:
                    st.error("Member name already exists!")
            else:
                st.warning("Please enter a name.")
                
    st.stop()

# --- MAIN APP ---
st.title(f"⛽ Petrol.py: Welcome, {st.session_state.username}!")

# --- SIDEBAR: CONTROLS ---
st.sidebar.markdown(f"**Logged in as:** `{st.session_state.username}`")
if st.sidebar.button("🚪 Log Out"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

cursor.execute("SELECT name FROM members")
members = [row[0] for row in cursor.fetchall()]
st.sidebar.markdown("---")
st.sidebar.write("**All Members:**", ", ".join(members))

# --- NAVIGATION TABS ---
tab1, tab2, tab3 = st.tabs(["🚀 Start Ride", "🏁 End Ride & Calculate", "📊 Ledger & History"])

# --- TAB 1: START RIDE ---
with tab1:
    st.header("Start a New Ride")
    
    cursor.execute("SELECT id, riders, start_time, start_odo FROM rides WHERE status = 'Ongoing'")
    ongoing_ride = cursor.fetchone()
    
    if ongoing_ride:
        active_id, active_riders, active_start_time, active_start_odo = ongoing_ride
        
        st.warning(f"⚠️ **Attention!** Active ongoing ride found (Started by **{active_riders}** at `{active_start_time}`).")
        st.info("You must close out the previous ride manually before starting a new one.")
        
        prev_end_odo = st.number_input("Enter Previous Ride's Ending Odometer (KM)", min_value=active_start_odo, step=0.1, key="prev_end_odo")
        petrol_price_prev = st.number_input("Today's Petrol Price (per Liter)", min_value=0.0, value=100.0, step=0.5, key="pp_prev")
        mileage_prev = st.number_input("Bike Mileage (KM per Liter)", min_value=5.0, value=45.0, step=1.0, key="m_prev")
        
        if st.button("🏁 Force End Previous Ride & Proceed"):
            if prev_end_odo <= active_start_odo:
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
                st.success(f"Previous ride successfully closed! Distance: {distance} KM. You can now start your ride below.")
                st.rerun()
                
    else:
        selected_riders = st.multiselect("Select Rider(s)", members, default=[st.session_state.username])
        start_odo = st.number_input("Enter Starting Odometer Reading (KM)", min_value=0.0, step=0.1)
        
        if st.button("🚀 Register & Start Ride"):
            if not selected_riders:
                st.error("Please select at least one rider.")
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
        st.write(f"**Starting Odometer Recorded:** {start_odo} KM")
        
        end_odo = st.number_input("Enter Ending Odometer Reading (KM)", min_value=start_odo, step=0.1)
        petrol_price = st.number_input("Today's Petrol Price (per Liter)", min_value=0.0, value=100.0, step=0.5)
        mileage = st.number_input("Bike Mileage (KM per Liter)", min_value=5.0, value=45.0, step=1.0)
        
        if st.button("🏁 Complete Ride & Calculate Split"):
            if end_odo <= start_odo:
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
