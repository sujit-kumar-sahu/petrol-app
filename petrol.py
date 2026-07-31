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
    
    # Rides table (distance tracking only)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            riders TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            start_odo REAL NOT NULL,
            end_odo REAL,
            distance REAL,
            status TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

conn = init_db()
cursor = conn.cursor()

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Petrol.py - Bike Distance Tracker", layout="wide")

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
tab1, tab2, tab3 = st.tabs(["🚀 Start Ride", "🏁 End Ride", "📊 Distance Ledger"])

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
        
        if st.button("🏁 Force End Previous Ride & Proceed"):
            if prev_end_odo <= active_start_odo:
                st.error("End odometer must be greater than start odometer.")
            else:
                end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                distance = prev_end_odo - active_start_odo
                
                cursor.execute("""
                    UPDATE rides 
                    SET end_time = ?, end_odo = ?, distance = ?, status = 'Completed'
                    WHERE id = ?
                """, (end_time, prev_end_odo, distance, active_id))
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
        
        if st.button("🏁 Complete Ride"):
            if end_odo <= start_odo:
                st.error("End odometer must be greater than start odometer.")
            else:
                end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                distance = end_odo - start_odo
                
                cursor.execute("""
                    UPDATE rides 
                    SET end_time = ?, end_odo = ?, distance = ?, status = 'Completed'
                    WHERE id = ?
                """, (end_time, end_odo, distance, ride_id))
                conn.commit()
                
                st.success(f"Ride completed! Total Distance: {distance} KM.")
                st.rerun()

# --- TAB 3: DISTANCE LEDGER ---
with tab3:
    st.header("📊 Ride History & Distance Breakdown")
    
    # Calculate overall total completed distance for metric view
    cursor.execute("SELECT SUM(distance) FROM rides WHERE status = 'Completed'")
    total_fleet_km_result = cursor.fetchone()[0]
    total_fleet_km = total_fleet_km_result if total_fleet_km_result else 0.0
    
    # Show high-level total metric card
    st.metric(label="🛣️ Total Fleet Distance Ran (All Completed Rides)", value=f"{total_fleet_km:.2f} KM")
    st.markdown("---")
    
    cursor.execute("SELECT id, riders, start_time, end_time, distance, status FROM rides")
    all_rides = cursor.fetchall()
    
    if all_rides:
        df_rides = pd.DataFrame(all_rides, columns=["ID", "Riders", "Start Time", "End Time", "Distance (KM)", "Status"])
        st.dataframe(df_rides, use_container_width=True)
    else:
        st.info("No ride history available yet.")
        
    st.subheader("💡 Member Distance Share & Percentage (%)")
    if all_rides:
        cursor.execute("SELECT riders, distance FROM rides WHERE status = 'Completed'")
        completed_rides = cursor.fetchall()
        
        distances_ran = {m: 0.0 for m in members}
        total_accumulated_distance = 0.0
        
        for riders_str, distance in completed_rides:
            if distance:
                riders_list = riders_str.split(",")
                trip_distance = distance
                total_accumulated_distance += trip_distance
                
                for rider in riders_list:
                    if rider in distances_ran:
                        distances_ran[rider] += trip_distance
                    
        summary_data = []
        for m in members:
            dist = distances_ran[m]
            pct = (dist / total_accumulated_distance * 100) if total_accumulated_distance > 0 else 0.0
            summary_data.append({
                "Member": m,
                "Total Distance Ran (KM)": round(dist, 2),
                "Share of Total KM (%)": f"{pct:.1f}%"
            })
            
        df_balance = pd.DataFrame(summary_data)
        st.dataframe(df_balance, use_container_width=True)
    else:
        st.write("No completed rides to calculate distance statistics.")
