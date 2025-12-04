# Auto-Room
## Brief
AutoRoom is a low-cost system that reduces wasted electricity
in enclosed spaces by combining real-time occupancy
detection with environmental sensing and automated load
control. It has an assistant to control the room from anywhere
The system dynamically recommends and controls air
conditioning and other loads to maximize energy savings while
preserving occupant comfort. The design targets classrooms,
meeting rooms, hostels, small offices, and homes.

<img width="350" height="200" alt="auto room project demo image" src="https://github.com/user-attachments/assets/1ee9ac8e-5030-4418-ba59-47fd9cc1b087" />

## Features 
- Live occupancy count and heat map on dashboard.
- Embedded assistant in the dashboard for text commands and suggestions.
- Smart AC suggestion card with recommended set point and estimated savings.
- Manual overrides and scheduled modes.
-
- Recallibration workflow to correct sensor drift

## Objectives
1. Accurate real-time occupancy tracking.
2. Autonomous control of lights, fans, ACs and other loads.
3. Smart AC suggestions and automatic control using DHT sensor readings and occupancy.
4. Usable web dashboard with embedded assistant, charts, and manual overrides.
5. Low cost and simple deployment.
6. Demonstrable energy and cost savings with measured metrics.

<img width="350" height="200" alt="project showing the lasers and dht sensor" src="https://github.com/user-attachments/assets/5284450d-eb26-49f1-8bda-ff685698b571" />

## Working
1. Two laser lights are installed on one side of the doorway,
and they are aligned with their corresponding LDR sensors
on the opposite side ofthe doorway. When a person crosses
the doorway, the beam interruption is read by the
Raspberry Pi input pin. If Laser 1 breaks before Laser 2, the
system detects an entry. If Laser 2 breaks before Laser 1,
the system detects an exit.

2. For AC, It recommends an AC setpoint from people count, indoor
temperature, and humidity; manual override always wins.
Core rules: empty → 27°C, one person → 25°C, more
people → cooler with reduced per-person penalty;
humidity >60% subtracts 0.5°C; clamp 18–27°C and nudge
+1°C if room is already at/near the target.

<img width="896" height="526" alt="image" src="https://github.com/user-attachments/assets/c5db873e-d0d7-420b-94a2-1282f4ef9bc0" />

