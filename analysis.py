import numpy as np
import pandas as pd
import streamlit as st
import pvlib
from pvlib.pvsystem import PVSystem, Array, FixedMount
from pvlib.modelchain import ModelChain
from pvlib.location import Location

# Set up browser page options
st.set_page_config(page_title="Solar Yield Engine", page_icon="☀️", layout="centered")

st.title("☀️ Solar Yield & Economic Analyzer")
st.markdown("Adjust the variables below to recalculate system performance in real-time.")

# --- PRESET LOCATIONS (Ghana) ---
# All Ghana locations share one timezone (Africa/Accra, GMT, no DST).
GHANA_LOCATIONS = {
    "Accra":      {"lat": 5.6037,  "lon": -0.1870, "alt": 65},
    "Kumasi":     {"lat": 6.6885,  "lon": -1.6244, "alt": 250},
    "Tamale":     {"lat": 9.4075,  "lon": -0.8393, "alt": 180},
    "Takoradi":   {"lat": 4.8845,  "lon": -1.7554, "alt": 40},
    "Cape Coast": {"lat": 5.1053,  "lon": -1.2466, "alt": 50},
    "Ho":         {"lat": 6.6000,  "lon": 0.4667,  "alt": 140},
}
TIMEZONE = "Africa/Accra"

# --- SIDEBAR CONTROL PANEL ---
st.sidebar.header("📍 Location")
city = st.sidebar.selectbox("Installation Site", list(GHANA_LOCATIONS.keys()))
loc = GHANA_LOCATIONS[city]
latitude, longitude, altitude = loc["lat"], loc["lon"], loc["alt"]

st.sidebar.header("🔧 System Configuration")
panel_count = st.sidebar.slider("Number of Solar Panels", min_value=1, max_value=50, value=10)
install_cost = st.sidebar.number_input("Total Installation Cost ($)", min_value=500, max_value=50000, value=3500, step=500)
elec_cost = st.sidebar.slider("Electricity Rate ($/kWh)", min_value=0.05, max_value=1.00, value=0.45, step=0.01)

st.sidebar.header("🔋 Battery Storage (optional)")
use_battery = st.sidebar.checkbox("Include battery storage", value=False)
if use_battery:
    battery_capacity = st.sidebar.slider("Battery Capacity (kWh)", min_value=1, max_value=40, value=10)
    battery_cost_per_kwh = st.sidebar.number_input("Battery Cost ($/kWh)", min_value=50, max_value=1000, value=300, step=10)
    daily_load = st.sidebar.slider("Estimated Daily Household Consumption (kWh)", min_value=1, max_value=60, value=10)
    net_metering = st.sidebar.checkbox("Grid offers net metering (credit for exports)?", value=False)
    feed_in_rate = st.sidebar.slider("Feed-in / Export Credit Rate ($/kWh)", min_value=0.0, max_value=elec_cost, value=elec_cost * 0.5, step=0.01) if net_metering else 0.0
else:
    battery_capacity = 0
    battery_cost_per_kwh = 0
    daily_load = 0
    net_metering = False
    feed_in_rate = 0.0

st.sidebar.header("🌍 Environmental Impact")
co2_factor = st.sidebar.number_input(
    "Grid Emission Factor (kg CO₂ / kWh)",
    min_value=0.0, max_value=1.2, value=0.40, step=0.01,
    help="Approximate figure for Ghana's grid mix (hydro + thermal). Adjust if you have a more precise local value."
)

# 1. Location Settings
site_location = Location(latitude, longitude, tz=TIMEZONE, altitude=altitude)


# 2. Compute Operations
@st.cache_data
def run_solar_simulation(lat, lon):
    pvgis_outputs = pvlib.iotools.get_pvgis_tmy(lat, lon, map_variables=True)
    df = pvgis_outputs
    df.index = pd.date_range(start='2026-01-01 00:00', end='2026-12-31 23:00', freq='h', tz=TIMEZONE)
    return df


try:
    weather_df = run_solar_simulation(latitude, longitude)

    # Hardware specs
    sandia_modules = pvlib.pvsystem.retrieve_sam('SandiaMod')
    cec_inverters = pvlib.pvsystem.retrieve_sam('cecinverter')
    module_specs = sandia_modules['Canadian_Solar_CS6X_300M__2013_']
    inverter_specs = cec_inverters['ABB__MICRO_0_25_I_OUTD_US_208__208V_']

    # Model Assembly
    mount = FixedMount(surface_tilt=latitude, surface_azimuth=180)
    array = Array(
        mount=mount,
        module_parameters=module_specs,
        modules_per_string=panel_count,
        temperature_model_parameters=pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass'],
    )
    system = PVSystem(arrays=[array], inverter_parameters=inverter_specs)

    # Calculate
    mc = ModelChain(system, site_location, spectral_model='no_loss', losses_model='no_loss')
    mc.run_model(weather_df)

    # Metrics Calculations (simple model: assumes all generation offsets the bill 1:1)
    hourly_ac = mc.results.ac  # Watts, hourly resolution -> numerically equal to Wh
    total_kwh = hourly_ac.sum() / 1000
    annual_savings = total_kwh * elec_cost
    payback = install_cost / annual_savings if annual_savings > 0 else 0
    co2_saved_simple = total_kwh * co2_factor

    # --- DISPLAY METRICS DASHBOARD ---
    col1, col2, col3 = st.columns(3)
    col1.metric("System Capacity", f"{panel_count * 0.3:.1f} kW", f"{panel_count} Panels")
    col2.metric("Annual Generation", f"{total_kwh:,.1f} kWh")
    col3.metric("Payback Period", f"{payback:.1f} Years")

    st.success(f"💰 Financial Return: This configuration saves **${annual_savings:,.2f}** per year!")
    st.info(f"🌍 Estimated CO₂ Avoided: **{co2_saved_simple:,.0f} kg/year** "
            f"(~{co2_saved_simple / 1000:,.1f} metric tons), based on a grid factor of {co2_factor:.2f} kg CO₂/kWh.")

    # Plot monthly data
    st.subheader("📊 Estimated Monthly Output Profiles")
    monthly_energy = hourly_ac.groupby(hourly_ac.index.month).sum() / 1000
    st.bar_chart(monthly_energy)

    # --- BATTERY / SELF-CONSUMPTION SIMULATION ---
    if use_battery:
        st.subheader("🔋 Battery & Self-Consumption Analysis")

        # Simple diurnal household load shape (residential double-peak: morning + evening)
        hourly_weights = np.array([
            0.020, 0.015, 0.015, 0.015, 0.020, 0.030, 0.045, 0.050,
            0.040, 0.035, 0.035, 0.035, 0.035, 0.035, 0.035, 0.035,
            0.040, 0.050, 0.065, 0.070, 0.065, 0.050, 0.035, 0.025,
        ])
        hourly_weights = hourly_weights / hourly_weights.sum()
        hourly_load = pd.Series(hourly_weights[hourly_ac.index.hour], index=hourly_ac.index) * daily_load

        gen_kwh = hourly_ac / 1000
        charge_eff = discharge_eff = np.sqrt(0.9)  # ~90% round-trip efficiency

        soc = 0.0
        self_direct = 0.0
        self_battery = 0.0
        grid_import = 0.0
        grid_export = 0.0
        monthly_import = {}
        monthly_export = {}

        for ts, gen, load in zip(hourly_ac.index, gen_kwh.values, hourly_load.values):
            month = ts.month
            if gen >= load:
                surplus = gen - load
                self_direct += load
                room = (battery_capacity - soc) / charge_eff
                charge_amt = min(surplus, room) if battery_capacity > 0 else 0.0
                soc += charge_amt * charge_eff
                exported = surplus - charge_amt
                grid_export += exported
                monthly_export[month] = monthly_export.get(month, 0.0) + exported
            else:
                deficit = load - gen
                self_direct += gen
                available = soc * discharge_eff
                discharge_amt = min(deficit, available) if battery_capacity > 0 else 0.0
                soc -= discharge_amt / discharge_eff
                self_battery += discharge_amt
                imported = deficit - discharge_amt
                grid_import += imported
                monthly_import[month] = monthly_import.get(month, 0.0) + imported

        total_self_consumption = self_direct + self_battery
        self_consumption_rate = (total_self_consumption / total_kwh * 100) if total_kwh > 0 else 0
        annual_load = daily_load * 365
        self_sufficiency_rate = (total_self_consumption / annual_load * 100) if annual_load > 0 else 0

        battery_cost = battery_capacity * battery_cost_per_kwh
        battery_savings = total_self_consumption * elec_cost + (grid_export * feed_in_rate if net_metering else 0)
        battery_payback = (install_cost + battery_cost) / battery_savings if battery_savings > 0 else 0

        bcol1, bcol2, bcol3 = st.columns(3)
        bcol1.metric("Self-Consumption Rate", f"{self_consumption_rate:.0f}%", "of solar generated")
        bcol2.metric("Self-Sufficiency Rate", f"{self_sufficiency_rate:.0f}%", "of household load")
        bcol3.metric("Payback w/ Battery", f"{battery_payback:.1f} Years")

        st.caption(
            f"Battery adds **${battery_cost:,.0f}** to upfront cost. "
            f"Annual grid import: {grid_import:,.0f} kWh · Annual export: {grid_export:,.0f} kWh"
            + (f" (credited at ${feed_in_rate:.2f}/kWh)" if net_metering else " (uncompensated, no net metering)")
        )

        if monthly_import or monthly_export:
            months = sorted(set(monthly_import) | set(monthly_export))
            grid_flow_df = pd.DataFrame({
                "Grid Import (kWh)": [monthly_import.get(m, 0.0) for m in months],
                "Grid Export (kWh)": [monthly_export.get(m, 0.0) for m in months],
            }, index=months)
            st.bar_chart(grid_flow_df)

        st.caption(
            "Note: this is a simplified model using a typical residential load curve, not your actual metered "
            "consumption. Treat results as directional, not a substitute for a professional battery sizing study."
        )

except Exception as e:
    st.error(f"Engine Exception Error: {e}")
