# Icarus
This code retrieves free meteorological data from the EU PVGIS API, builds a physical model of a solar panel array, and calculates the expected AC power output.
☀️ Solar Yield & Economic Analyzer
A Streamlit app that models rooftop solar performance and payback for sites in Ghana, using
pvlib and PVGIS typical-year weather data.
Features
Location picker — choose from preset Ghana cities (Accra, Kumasi, Tamale, Takoradi,
Cape Coast, Ho). Each preset carries its own latitude/longitude/altitude; all share Ghana's
single timezone (`Africa/Accra`).
System sizing — adjust panel count, installation cost, and local electricity rate to see
generation, savings, and payback update live.
Battery & self-consumption modeling (optional) — enable a battery to simulate hour-by-hour
charge/discharge against a typical residential load curve, sized to your estimated daily
consumption. Reports self-consumption rate, self-sufficiency rate, and a battery-adjusted
payback period.
Net metering toggle — model whether exported surplus energy earns a feed-in credit or is
uncompensated.
CO₂ impact estimate — approximate annual avoided grid emissions, using an editable grid
emission factor (kg CO₂/kWh) since the real value depends on Ghana's generation mix at the time.
Running locally
```bash
pip install -r requirements.txt
streamlit run analysis.py
```
The first run for a given location fetches a PVGIS typical-meteorological-year dataset over the
network and caches it (`@st.cache\_data`), so subsequent tweaks to panel count, pricing, or battery
settings recalculate instantly without re-fetching weather data.
Model notes & assumptions
Generation modeling uses a fixed-tilt array (`surface\_tilt = latitude`, `surface\_azimuth = 180`,
i.e. facing south) with Sandia module and CEC inverter parameters, and no spectral/derate losses
(`spectral\_model='no\_loss'`, `losses\_model='no\_loss'`) — real-world output will typically be
somewhat lower due to soiling, wiring, and shading losses not modeled here.
The battery simulation uses a simplified, fixed diurnal household load shape (a residential
double-peak: morning and evening) scaled to your estimated daily consumption — it is not
based on your actual metered load profile, so treat results as directional.
Round-trip battery efficiency is fixed at ~90%.
The CO₂ emission factor is a rough default and should be adjusted if you have a more precise or
current figure for your grid.
Possible next steps
Support uploading an actual hourly/interval load profile (e.g. from a smart meter export) instead
of the synthetic diurnal shape.
Add panel degradation and multi-year cash-flow / NPV projections instead of a simple payback
period.
Let users choose module/inverter models instead of a single hardcoded pair.
Add tilt/azimuth as sliders for non-optimal roof orientations.
