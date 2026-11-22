-- Seed: WaterWatch demo incidents for Bengaluru
-- ALL rows are is_simulated = TRUE and labelled as demo data
-- Neighbourhoods: Jayanagar, Koramangala, Indiranagar, Whitefield, HSR Layout, Malleshwaram, BTM Layout

INSERT INTO water_incidents
  (incident_type, geom, severity, confidence, verification_status,
   affected_route, evidence, source, recommended_action, area_name,
   observed_at, expires_at, is_simulated)
VALUES
  (
    'supply_disruption',
    ST_SetSRID(ST_MakePoint(77.5832, 12.9299), 4326)::geography,
    'high', 0.85, 'reported',
    false,
    ARRAY['12 community reports in last 2 hrs', 'BWSSB maintenance notice #2024-1182'],
    ARRAY['community_reports', 'bwssb_mock'],
    'Supply cut expected for 18 hrs near Jayanagar 4th Block. Store water now. Tanker available at BBMP ward office.',
    'Jayanagar',
    NOW() - INTERVAL '1 hour',
    NOW() + INTERVAL '17 hours',
    TRUE
  ),
  (
    'tanker_shortage',
    ST_SetSRID(ST_MakePoint(77.6232, 12.9352), 4326)::geography,
    'moderate', 0.72, 'reported',
    false,
    ARRAY['Tanker operator reports 4-hr delay', '5 residents reported no tanker arrival'],
    ARRAY['tanker_mock', 'community_reports'],
    'Tanker delayed by 4 hrs near Koramangala 5th Block. Contact ward tanker helpline: 080-22221111.',
    'Koramangala',
    NOW() - INTERVAL '30 minutes',
    NOW() + INTERVAL '4 hours',
    TRUE
  ),
  (
    'sensor_anomaly',
    ST_SetSRID(ST_MakePoint(77.6408, 12.9784), 4326)::geography,
    'moderate', 0.78, 'predicted',
    false,
    ARRAY['Pressure sensor ESP32-IND-001 reading 0.4 bar (normal: 1.2 bar)', 'Flow rate down 60%'],
    ARRAY['iot_sensor_mock'],
    'Low water pressure detected near Indiranagar 100 Feet Road. Possible main pipe issue. Monitor your taps.',
    'Indiranagar',
    NOW() - INTERVAL '15 minutes',
    NOW() + INTERVAL '6 hours',
    TRUE
  ),
  (
    'demand_spike',
    ST_SetSRID(ST_MakePoint(77.7480, 12.9698), 4326)::geography,
    'low', 0.65, 'predicted',
    false,
    ARRAY['Demand 40% above daily average for Whitefield zone', 'Industrial usage spike detected'],
    ARRAY['bwssb_mock'],
    'High demand period in Whitefield. Supply may be reduced during 2–5 PM. Use stored water if possible.',
    'Whitefield',
    NOW() - INTERVAL '45 minutes',
    NOW() + INTERVAL '3 hours',
    TRUE
  ),
  (
    'supply_disruption',
    ST_SetSRID(ST_MakePoint(77.6414, 12.9081), 4326)::geography,
    'critical', 0.92, 'confirmed',
    false,
    ARRAY['BWSSB confirmed main pipe burst on 27th Main', 'Repair crew dispatched at 06:00 AM', '23 community reports'],
    ARRAY['bwssb_mock', 'community_reports'],
    'Main pipe burst on 27th Main, HSR Layout. Supply cut for up to 36 hrs. Emergency tankers dispatched to sectors 1 and 2.',
    'HSR Layout',
    NOW() - INTERVAL '2 hours',
    NOW() + INTERVAL '34 hours',
    TRUE
  ),
  (
    'supply_disruption',
    ST_SetSRID(ST_MakePoint(77.5713, 13.0033), 4326)::geography,
    'low', 0.60, 'reported',
    false,
    ARRAY['3 resident reports of low pressure', 'No BWSSB notice issued yet'],
    ARRAY['community_reports'],
    'Low pressure reported near Malleshwaram 18th Cross. No official notice yet. Check back in 2 hrs.',
    'Malleshwaram',
    NOW() - INTERVAL '20 minutes',
    NOW() + INTERVAL '2 hours',
    TRUE
  ),
  (
    'tanker_shortage',
    ST_SetSRID(ST_MakePoint(77.6099, 12.9166), 4326)::geography,
    'high', 0.80, 'reported',
    false,
    ARRAY['No tanker supply for 2 days in BTM Layout Sector 3', '8 community reports', 'Ward councillor alert'],
    ARRAY['tanker_mock', 'community_reports'],
    'No tanker supply for 48 hrs in BTM Layout Sector 3. File complaint at BWSSB helpline 1916. Emergency water kiosk open at BTM 2nd Stage park.',
    'BTM Layout',
    NOW() - INTERVAL '3 hours',
    NOW() + INTERVAL '21 hours',
    TRUE
  );
