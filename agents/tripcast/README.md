# TripCast

Predicts the trip time you will actually experience, and suggests alternative roads.

**The idea:** a time shown at departure assumes traffic stays as it is when you leave. TripCast costs each
road step at the moment you will reach it, so a trip that starts in light traffic but runs into the peak
gets a longer, more honest estimate. It also shows the best time to leave.

- Routes and alternatives: OSRM on OpenStreetMap data (real roads, free-flow durations, no traffic).
- Traffic: an **assumed** time-of-day profile (`tripcast/profile.py`). These numbers are not measured Bengaluru data;
  replace them with values from real observations. With `TOMTOM_API_KEY` set, live flow adjusts the near-term part
  of the trip and fades back to the profile. Without a key the response says it uses the assumed profile only.
- Road hazards on each route come from RoadTrust (`ROADTRUST_URL`); a route with a reported closure is not recommended.
- The accuracy of predictions has not been measured. Validate against real trips before relying on them.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
.venv/bin/uvicorn tripcast.api:create_app --factory --port 8003
```
