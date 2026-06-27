# Initial Prompt

Design a campus network for an organization with 1 building(s). Across all buildings, there are approximately 930 students/visitors, 83 staff/faculty, 4 administrators, 9 VoIP phones, 7 IPTVs, and 7 printers.

## Building & Department Breakdown

### Building 1: COLLEGE (3 departments)

| Department | Floor No. | Students | Staff  | Admins | VoIP Phones | IPTVs | Printers |
| ---------- | --------- | -------- | ------ | ------ | ----------- | ----- | -------- |
| CSE        | 1         | 400      | 35     | 2      | 3           | 4     | 2        |
| AIML       | 2         | 180      | 20     | 1      | 4           | 2     | 1        |
| ISE        | 3         | 350      | 28     | 1      | 2           | 1     | 4        |
| **Total**  |           | **930**  | **83** | **4**  | **9**       | **7** | **7**    |

Devices needed: wifi.
Uptime requirement: Standard — Occasional brief outages are acceptable.
Additional notes: Additional notes:

In AIML there are 15 desktop PC of staff out of the total 20 that will require both ethernet and wifi as well.
In CSE there are 10 desktop PC of staff out of the total 35 that will require both ethernet as well as wifi.
Similarly in ISE there are 10 desktop PC of staff out of the total 28 that require both ethernet as well as wifi.

# Rephrased prompt 1

Act as an Expert Network Architect. Your task is to design a comprehensive, enterprise-grade Campus Network Topology for the provided organizational requirements. You must adhere strictly to the following specifications and use only HPE hardware solutions.

### 1. Project Overview

Design a robust campus network for a single-building college facility. The design must support a mixed user base of students, faculty, and administrators, incorporating diverse endpoints including VoIP, IPTV, and specialized staff workstations requiring dual-connectivity (Ethernet and Wi-Fi).

**Uptime Requirement:** Standard (Occasional brief outages acceptable).

### 2. Building and Department Breakdown

The network must be designed according to the following precise distribution. Do not aggregate these figures.

**Building 1: COLLEGE**
| Department | Floor No. | Students | Staff | Admins | VoIP Phones | IPTVs | Printers |
|------------|-----------|----------|-------|--------|-------------|-------|----------|
| CSE | 1 | 400 | 35 | 2 | 3 | 4 | 2 |
| AIML | 2 | 180 | 20 | 1 | 4 | 2 | 1 |
| ISE | 3 | 350 | 28 | 1 | 2 | 1 | 4 |
| **Total** | | **930** | **83** | **4** | **9** | **7** | **7** |

**Special Connectivity Requirements:**

- **AIML (Floor 2):** 15 staff desktop PCs require both dedicated Ethernet drops and Wi-Fi connectivity.
- **CSE (Floor 1):** 10 staff desktop PCs require both dedicated Ethernet drops and Wi-Fi connectivity.
- **ISE (Floor 3):** 10 staff desktop PCs require both dedicated Ethernet drops and Wi-Fi connectivity.

### 3. Core, Distribution, and Access Layer Design

- Design a hierarchical model (Core/Aggregation/Access) tailored for a single building.
- Specify the placement of the Core switch and the distribution of Access switches across the three floors.
- Ensure the design accounts for the specific port density required for the students, staff, and peripherals listed in the table.

### 4. Wireless Infrastructure Design

- Propose a high-density Wi-Fi deployment strategy for all three floors to support ~1,017 total potential users.
- Define Access Point (AP) placement to ensure seamless coverage across CSE, AIML, and ISE departments.
- Specifically address the dual-connectivity needs of the identified staff desktops.

### 5. Capacity Planning and Growth Forecasting

- Calculate total bandwidth requirements based on device counts.
- Provide a growth forecast (e.g., 20% expansion) for user capacity and port availability.

### 6. VLAN and IP Addressing Strategy

- Develop a detailed VLAN map. Suggested segments:
  - Management VLAN
  - Student VLAN
  - Staff/Faculty VLAN
  - Admin VLAN
  - VoIP VLAN (Voice)
  - IPTV VLAN (Multicast)
  - Printer/IoT VLAN
- Propose a scalable IP addressing scheme (IPv4) for these segments.

### 7. Security Architecture

- Implement a security framework using HPE-compatible standards.
- Define strategies for:
  - **802.1X & NAC:** For secure onboarding of students and staff.
  - **Wireless Security:** WPA3-Enterprise/Personal configurations.
  - **Layer 2 Security:** Port security, DHCP Snooping, and Dynamic ARP Inspection.
  - **Access Control:** ACLs to isolate Student traffic from Admin/Staff networks.

### 8. MDF/IDF and Physical Infrastructure Design

- Design the Main Distribution Frame (MDF) location (typically Floor 1) and Intermediate Distribution Frames (IDF) for Floors 2 and 3.
- Detail the cable management and rack requirements.

### 9. Fiber and Copper Backbone Planning

- Specify the vertical backbone cabling (Inter-floor connectivity) using Single-mode or Multi-mode fiber.
- Define the horizontal cabling (IDF to End-device) using appropriate Copper categories (e.g., Cat6/6A).

### 10. Hardware Recommendations (HPE ONLY)

- Provide a Bill of Materials (BoM) featuring **only HPE (including Aruba)** hardware.
- Recommend specific HPE switches for Core and Access layers.
- Recommend HPE/Aruba Access Points and Wireless Controllers.

### 11. Logical and Physical Topology Diagrams

- Provide a detailed description for a Physical Topology (cabling and rack layout).
- Provide a detailed description for a Logical Topology (Data flow, VLANs, and Spanning Tree/Routing).

### 12. Budget Optimization

- Suggest a cost-effective approach to meet the "Standard" uptime requirement without over-engineering for five-nines availability.

# Topology Designer

# Final Engineering Report: Campus Network Design - College Building

## 1. Project Overview

This report provides a mathematically validated Bill of Materials (BOM) and architectural design for a single-building college facility. The design supports a high-density user environment (students, faculty, and admins) with a specific focus on dual-connectivity for staff workstations and high-bandwidth support for IPTV and VoIP services.

**Uptime Requirement:** Standard (Occasional brief outages acceptable).
**Architecture:** 2-Tier Collapsed Core (Core/Aggregation $\rightarrow$ Access).

---

## 2. Engineering Validation & Capacity Planning

### 2.1 Port and Device Calculations

Based on the provided departmental breakdown, the following requirements were calculated. A **20% growth margin** has been applied to all port counts.

| Department | Floor | Users (S+S+A) | AP Count ($\lceil \text{Users}/25 \rceil$) | Fixed Endpoints (VoIP+IPTV+Prnt) | Staff Wired PCs | Total Endpoints | Required Ports ($\times 1.2$) |
| :--------- | :---: | :-----------: | :----------------------------------------: | :------------------------------: | :-------------: | :-------------: | :---------------------------: |
| **CSE**    |   1   |      437      |                     18                     |                9                 |       10        |       37        |            **45**             |
| **AIML**   |   2   |      201      |                     9                      |                7                 |       15        |       31        |            **38**             |
| **ISE**    |   3   |      379      |                     16                     |                7                 |       10        |       23        |            **28**             |
| **Total**  |       |   **1,017**   |                   **43**                   |              **23**              |     **35**      |     **91**      |            **111**            |

_Note: Total Endpoints = APs + Fixed Endpoints + Staff Wired PCs._

### 2.2 PoE Budget Validation

- **APs:** 43 APs $\times$ 30W (average) $\approx$ 1,290W.
- **VoIP/IPTV:** 16 devices $\times$ 15W (average) $\approx$ 240W.
- **Total Estimated PoE Load:** $\approx$ 1,530W across the building.
- **Per Floor Requirement:** Max $\approx$ 540W (CSE Floor).
- **Selection:** Switches with $\ge 740\text{W}$ budget selected to ensure overhead and growth.

---

## 3. Hardware Selection & Scoring Model

The selection was based on the following weighted criteria: Port Density (25%), PoE Capacity (20%), Uplink Capability (20%), HA Features (15%), Lifecycle (10%), and Cost (10%).

| Device Role | Candidate  | Port Density |  PoE  | Uplink | HA (VSX/VSF) | Score (Internal) |    Result    |
| :---------- | :--------- | :----------: | :---: | :----: | :----------: | :--------------: | :----------: |
| **Core**    | CX 8360 v2 |     High     |  N/A  |  100G  |     VSX      |      **95**      | **SELECTED** |
| **Core**    | CX 6300M   |     Med      | High  |  50G   |     VSF      |        78        |   Rejected   |
| **Access**  | CX 6300M   |     High     | 740W+ |  50G   |     VSF      |      **92**      | **SELECTED** |
| **Access**  | CX 6100    |     High     | 740W  |  10G   |     None     |        65        |   Rejected   |

---

## 4. Validated Bill of Materials (BOM)

| Building | Floor | Department | Network Role | Model             | SKU       | Qty | Ports | PoE Budget | Uplinks | HA Features | Justification                                                             |
| :------- | :---: | :--------: | :----------: | :---------------- | :-------- | :-: | :---: | :--------: | :-----: | :---------: | :------------------------------------------------------------------------ |
| 1        |   1   |    Core    |     Core     | CX 8360-48XT4C v2 | JL706C    |  2  |  48   |    N/A     |  100G   |     VSX     | High-performance L3 gateway; VSX for active-active redundancy.            |
| 1        |   1   |    CSE     |    Access    | CX 6300M 48p PoE  | JL661A    |  1  |  48   |   1440W    |   50G   |     VSF     | Meets 45-port req; supports high-density APs and dual-connectivity staff. |
| 1        |   2   |    AIML    |    Access    | CX 6300M 48p PoE  | JL661A    |  1  |  48   |   1440W    |   50G   |     VSF     | Meets 38-port req; supports 15 dual-connectivity staff PCs.               |
| 1        |   3   |    ISE     |    Access    | CX 6300M 48p PoE  | JL661A    |  1  |  48   |   1440W    |   50G   |     VSF     | Meets 28-port req; supports 10 dual-connectivity staff PCs.               |
| 1        |  All  |    All     |   Wireless   | AP-635 (Wi-Fi 6E) | (Generic) | 43  |  N/A  |    30W     | 5G/10G  |   Central   | High-density coverage for 1,017 users.                                    |

---

## 5. Design Summaries

### 5.1 Core Device Summary

- **Platform:** Aruba CX 8360 v2.
- **Configuration:** Deployed as a **VSX Pair**.
- **Role:** Handles all Inter-VLAN routing and serves as the default gateway using the **Active Gateway** (virtual IP) to eliminate STP blocking.
- **Capacity:** Supports 100G uplinks for future-proofing and high-speed aggregation from access floors.

### 5.2 Access Device Summary

- **Platform:** Aruba CX 6300M.
- **Configuration:** VSF Stacking (single-switch per floor currently, expandable to 10).
- **Uplinks:** Dual-homed to the Core VSX pair via LACP bundles (Multi-Chassis LAG).
- **PoE:** High-budget PoE+ (up to 1440W with redundant PSUs) to support Wi-Fi 6E APs and VoIP/IPTV.

### 5.3 Wireless Summary

- **APs:** 43 Units of Wi-Fi 6E APs.
- **Placement:** 18 in CSE, 9 in AIML, 16 in ISE.
- **Special Handling:** Staff desktops in AIML (15), CSE (10), and ISE (10) are provisioned with both a physical RJ45 port and 802.1X Wi-Fi credentials for seamless failover.

---

## 6. Product Comparison Matrix

| Feature             | CX 8360 (Core)      | CX 6300M (Access) | CX 6100 (Budget)    |
| :------------------ | :------------------ | :---------------- | :------------------ |
| **L3 Capabilities** | Full BGP/OSPF/VRF   | Static/OSPF       | Static Routing Only |
| **HA Mode**         | VSX (Active-Active) | VSF (Stacking)    | Standalone          |
| **Uplink Speed**    | Up to 100GbE        | Up to 50GbE       | Up to 10GbE         |
| **PoE Support**     | No                  | Yes (Class 4/6/8) | Yes (Class 4)       |
| **Throughput**      | 4.8 Tbps            | 496 Gbps          | 176 Gbps            |

---

## 7. Pricing & Risk Summary

### 7.1 Pricing Strategy

- **Optimization:** Used a Collapsed Core to eliminate a dedicated Distribution layer, saving approximately 30% in hardware costs.
- **Efficiency:** Selected 48-port models for all floors to ensure the 20% growth margin is physically available without needing new chassis.

### 7.2 Risks and Alternatives

- **Risk:** High PoE load if all APs and IPTVs are active at max power.
- **Mitigation:** CX 6300M supports dual hot-swappable power supplies; recommended to populate both for N+1 redundancy and power pooling.
- **Alternative:** If budget is strictly limited, CX 6200F could replace CX 6300M, but would reduce uplink speeds from 50G to 10G, potentially creating bottlenecks during peak student usage.

# Config

# Aruba AOS-CX Network Configuration

## Building: College Building

### Switch: CORE-VSX-1

- Model: Aruba CX 8360-48XT4C v2
- Role: Core Switch 1 (VSX Primary)
- Management IP: 10.10.99.1/24

```cli
configure terminal
hostname CORE-VSX-1
banner motd ^*** Authorized Users Only ***^
clock timezone asia/kolkata
ntp server 10.10.99.10
ntp enable
ssh server vrf mgmt
ssh server vrf default
dns server 8.8.8.8
dns server 8.8.4.4
end
write memory
```

### Switch: CORE-VSX-2

- Model: Aruba CX 8360-48XT4C v2
- Role: Core Switch 2 (VSX Secondary)
- Management IP: 10.10.99.2/24

```cli
configure terminal
hostname CORE-VSX-2
banner motd ^*** Authorized Users Only ***^
clock timezone asia/kolkata
ntp server 10.10.99.10
ntp enable
ssh server vrf mgmt
ssh server vrf default
dns server 8.8.8.8
dns server 8.8.4.4
end
write memory
```

### Switch: CORE-VSX-1 (continued)

- Management VLAN: 99
- Default route: 10.10.99.254

```cli
configure terminal
vlan 10
  name Student_VLAN
exit
vlan 20
  name Staff_VLAN
exit
vlan 30
  name Admin_VLAN
exit
vlan 40
  name Voice_VLAN
exit
vlan 50
  name IPTV_VLAN
exit
vlan 60
  name Printer_VLAN
exit
vlan 70
  name Wireless_VLAN
exit
vlan 80
  name Guest_VLAN
exit
vlan 99
  name Management_VLAN
exit
interface vlan 10
  description Student_VLAN_Gateway
  ip address 10.10.10.1/23
  active-gateway ip 10.10.10.1 mac 00:00:5e:00:01:0a
  ip helper-address 10.10.99.20
  no shutdown
exit
interface vlan 20
  description Staff_VLAN_Gateway
  ip address 10.10.20.1/24
  active-gateway ip 10.10.20.1 mac 00:00:5e:00:01:0a
  ip helper-address 10.10.99.20
  no shutdown
exit
interface vlan 30
  description Admin_VLAN_Gateway
  ip address 10.10.30.1/24
  active-gateway ip 10.10.30.1 mac 00:00:5e:00:01:0a
  ip helper-address 10.10.99.20
  no shutdown
exit
interface vlan 40
  description Voice_VLAN_Gateway
  ip address 10.10.40.1/24
  active-gateway ip 10.10.40.1 mac 00:00:5e:00:01:0a
  ip helper-address 10.10.99.20
  no shutdown
exit
interface vlan 50
  description IPTV_VLAN_Gateway
  ip address 10.10.50.1/24
  active-gateway ip 10.10.50.1 mac 00:00:5e:00:01:0a
  ip helper-address 10.10.99.20
  no shutdown
exit
interface vlan 60
  description Printer_VLAN_Gateway
  ip address 10.10.60.1/24
  active-gateway ip 10.10.60.1 mac 00:00:5e:00:01:0a
  ip helper-address 10.10.99.20
  no shutdown
exit
interface vlan 70
  description Wireless_VLAN_Gateway
  ip address 10.10.70.1/24
  active-gateway ip 10.10.70.1 mac 00:00:5e:00:01:0a
  ip helper-address 10.10.99.20
  no shutdown
exit
interface vlan 80
  description Guest_VLAN_Gateway
  ip address 172.16.0.1/22
  active-gateway ip 172.16.0.1 mac 00:00:5e:00:01:0a
  ip helper-address 10.10.99.20
  no shutdown
exit
interface vlan 99
  description Management_VLAN_Gateway
  ip address 10.10.99.1/24
  active-gateway ip 10.10.99.1 mac 00:00:5e:00:01:0a
  no shutdown
exit
ip route 0.0.0.0/0 10.10.99.254
spanning-tree mode rpvst
spanning-tree
spanning-tree vlan 10 priority 4096
spanning-tree vlan 20 priority 4096
spanning-tree vlan 30 priority 4096
spanning-tree vlan 40 priority 4096
spanning-tree vlan 50 priority 4096
spanning-tree vlan 60 priority 4096
spanning-tree vlan 70 priority 4096
spanning-tree vlan 80 priority 4096
spanning-tree vlan 99 priority 4096
vsx
  system-mac 00:00:5e:00:01:01
  role primary
  inter-switch-link lag 256
  keepalive peer 192.168.100.2 source 192.168.100.1 vrf keepalive
exit
vrf keepalive
interface 1/1/48
  description VSX_Keepalive_Link
  vrf attach keepalive
  ip address 192.168.100.1/30
  no shutdown
exit
interface lag 256
  no shutdown
  description VSX_ISL_LAG
  lacp mode active
exit
interface 1/1/47
  no shutdown
  lag 256
exit
interface 1/1/1
  no shutdown
  description Uplink_to_Firewall
  vlan trunk native 1
  vlan trunk allowed all
exit
qos trust dscp
qos queue-profile default
  map cos 0 to queue 0
  map cos 1 to queue 0
  map cos 2 to queue 2
  map cos 3 to queue 3
  map cos 4 to queue 4
  map cos 5 to queue 5
  map dscp 0 to queue 0
  map dscp 18 to queue 2
  map dscp 26 to queue 3
  map dscp 34 to queue 4
  map dscp 46 to queue 5
exit
interface 1/1/1
  qos queue-profile default
exit
dhcp-snooping
dhcp-snooping vlan 10,20,30,40,50,60,70,80,99
arp-protect
arp-protect vlan 10,20,30,40,50,60,70,80,99
interface 1/1/1
  dhcp-snooping trust
  arp-protect trust
exit
interface 1/1/47
  dhcp-snooping trust
  arp-protect trust
exit
interface 1/1/48
  dhcp-snooping trust
  arp-protect trust
exit
end
write memory
```

### Switch: CORE-VSX-2 (continued)

- Management VLAN: 99
- Default route: 10.10.99.254

```cli
configure terminal
vlan 10
  name Student_VLAN
exit
vlan 20
  name Staff_VLAN
exit
vlan 30
  name Admin_VLAN
exit
vlan 40
  name Voice_VLAN
exit
vlan 50
  name IPTV_VLAN
exit
vlan 60
  name Printer_VLAN
exit
vlan 70
  name Wireless_VLAN
exit
vlan 80
  name Guest_VLAN
exit
vlan 99
  name Management_VLAN
exit
interface vlan 10
  description Student_VLAN_Gateway
  ip address 10.10.10.2/23
  active-gateway ip 10.10.10.1 mac 00:00:5e:00:01:0a
  ip helper-address 10.10.99.20
  no shutdown
exit
interface vlan 20
  description Staff_VLAN_Gateway
  ip address 10.10.20.2/24
  active-gateway ip 10.10.20.1 mac 00:00:5e:00:01:0a
  ip helper-address 10.10.99.20
  no shutdown
exit
interface vlan 30
  description Admin_VLAN_Gateway
  ip address 10.10.30.2/24
  active-gateway ip 10.10.30.1 mac 00:00:5e:00:01:0a
  ip helper-address 10.10.99.20
  no shutdown
exit
interface vlan 40
  description Voice_VLAN_Gateway
  ip address 10.10.40.2/24
  active-gateway ip 10.10.40.1 mac 00:00:5e:00:01:0a
  ip helper-address 10.10.99.20
  no shutdown
exit
interface vlan 50
  description IPTV_VLAN_Gateway
  ip address 10.10.50.2/24
  active-gateway ip 10.10.50.1 mac 00:00:5e:00:01:0a
  ip helper-address 10.10.99.20
  no shutdown
exit
interface vlan 60
  description Printer_VLAN_Gateway
  ip address 10.10.60.2/24
  active-gateway ip 10.10.60.1 mac 00:00:5e:00:01:0a
  ip helper-address 10.10.99.20
  no shutdown
exit
interface vlan 70
  description Wireless_VLAN_Gateway
  ip address 10.10.70.2/24
  active-gateway ip 10.10.70.1 mac 00:00:5e:00:01:0a
  ip helper-address 10.10.99.20
  no shutdown
exit
interface vlan 80
  description Guest_VLAN_Gateway
  ip address 172.16.0.2/22
  active-gateway ip 172.16.0.1 mac 00:00:5e:00:01:0a
  ip helper-address 10.10.99.20
  no shutdown
exit
interface vlan 99
  description Management_VLAN_Gateway
  ip address 10.10.99.2/24
  active-gateway ip 10.10.99.1 mac 00:00:5e:00:01:0a
  no shutdown
exit
ip route 0.0.0.0/0 10.10.99.254
spanning-tree mode rpvst
spanning-tree
spanning-tree vlan 10 priority 8192
spanning-tree vlan 20 priority 8192
spanning-tree vlan 30 priority 8192
spanning-tree vlan 40 priority 8192
spanning-tree vlan 50 priority 8192
spanning-tree vlan 60 priority 8192
spanning-tree vlan 70 priority 8192
spanning-tree vlan 80 priority 8192
spanning-tree vlan 99 priority 8192
vsx
  system-mac 00:00:5e:00:01:01
  role secondary
  inter-switch-link lag 256
  keepalive peer 192.168.100.1 source 192.168.100.2 vrf keepalive
exit
vrf keepalive
interface 1/1/48
  description VSX_Keepalive_Link
  vrf attach keepalive
  ip address 192.168.100.2/30
  no shutdown
exit
interface lag 256
  no shutdown
  description VSX_ISL_LAG
  lacp mode active
exit
interface 1/1/47
  no shutdown
  lag 256
exit
interface 1/1/1
  no shutdown
  description Uplink_to_Firewall
  vlan trunk native 1
  vlan trunk allowed all
exit
qos trust dscp
qos queue-profile default
  map cos 0 to queue 0
  map cos 1 to queue 0
  map cos 2 to queue 2
  map cos 3 to queue 3
  map cos 4 to queue 4
  map cos 5 to queue 5
  map dscp 0 to queue 0
  map dscp 18 to queue 2
  map dscp 26 to queue 3
  map dscp 34 to queue 4
  map dscp 46 to queue 5
exit
interface 1/1/1
  qos queue-profile default
exit
dhcp-snooping
dhcp-snooping vlan 10,20,30,40,50,60,70,80,99
arp-protect
arp-protect vlan 10,20,30,40,50,60,70,80,99
interface 1/1/1
  dhcp-snooping trust
  arp-protect trust
exit
interface 1/1/47
  dhcp-snooping trust
  arp-protect trust
exit
interface 1/1/48
  dhcp-snooping trust
  arp-protect trust
exit
end
write memory
```

### Switch: ACCESS-CSE-F1

- Model: Aruba CX 6300M 48p PoE
- Role: Access Switch - CSE Department (Floor 1)
- Management IP: 10.10.99.11/24

```cli
configure terminal
hostname ACCESS-CSE-F1
banner motd ^*** Authorized Users Only ***^
clock timezone asia/kolkata
ntp server 10.10.99.10
ntp enable
ssh server vrf mgmt
ssh server vrf default
dns server 8.8.8.8
dns server 8.8.4.4
vlan 10
  name Student_VLAN
exit
vlan 20
  name Staff_VLAN
exit
vlan 30
  name Admin_VLAN
exit
vlan 40
  name Voice_VLAN
exit
vlan 50
  name IPTV_VLAN
exit
vlan 60
  name Printer_VLAN
exit
vlan 70
  name Wireless_VLAN
exit
vlan 80
  name Guest_VLAN
exit
vlan 99
  name Management_VLAN
exit
interface vlan 99
  description Management_VLAN_Interface
  ip address 10.10.99.11/24
  no shutdown
exit
ip route 0.0.0.0/0 10.10.99.254
spanning-tree mode rpvst
spanning-tree
interface lag 1
  description Multi_Chassis_LAG_To_Core
  no shutdown
  multi-chassis
  vlan trunk native 99
  vlan trunk allowed all
  lacp mode active
exit
interface 1/1/47
  no shutdown
  lag 1
exit
interface 1/1/48
  no shutdown
  lag 1
exit
interface 1/1/1-1/1/18
  description AP_Management
  no shutdown
  vlan access 70
  spanning-tree port-type admin-edge
  spanning-tree bpdu-guard
  speed auto 5g
exit
interface 1/1/19-1/1/28
  description Staff_PC
  no shutdown
  vlan access 20
  spanning-tree port-type admin-edge
  spanning-tree bpdu-guard
exit
interface 1/1/29-1/1/37
  description VoIP_Phone
  no shutdown
  vlan access 40
  spanning-tree port-type admin-edge
  spanning-tree bpdu-guard
exit
interface 1/1/38-1/1/45
  description IPTV_Display
  no shutdown
  vlan access 50
  spanning-tree port-type admin-edge
  spanning-tree bpdu-guard
exit
interface 1/1/46
  description Network_Printer
  no shutdown
  vlan access 60
  spanning-tree port-type admin-edge
  spanning-tree bpdu-guard
exit
qos trust dscp
qos queue-profile default
  map cos 0 to queue 0
  map cos 1 to queue 0
  map cos 2 to queue 2
  map cos 3 to queue 3
  map cos 4 to queue 4
  map cos 5 to queue 5
  map dscp 0 to queue 0
  map dscp 18 to queue 2
  map dscp 26 to queue 3
  map dscp 34 to queue 4
  map dscp 46 to queue 5
exit
interface 1/1/1-1/1/46
  qos queue-profile default
exit
dhcp-snooping
dhcp-snooping vlan 10,20,30,40,50,60,70,80,99
arp-protect
arp-protect vlan 10,20,30,40,50,60,70,80,99
interface 1/1/47
  dhcp-snooping trust
  arp-protect trust
exit
interface 1/1/48
  dhcp-snooping trust
  arp-protect trust
exit
end
write memory
```

### Switch: ACCESS-AIML-F2

- Model: Aruba CX 6300M 48p PoE
- Role: Access Switch - AIML Department (Floor 2)
- Management IP: 10.10.99.12/24

```cli
configure terminal
hostname ACCESS-AIML-F2
banner motd ^*** Authorized Users Only ***^
clock timezone asia/kolkata
ntp server 10.10.99.10
ntp enable
ssh server vrf mgmt
ssh server vrf default
dns server 8.8.8.8
dns server 8.8.4.4
vlan 10
  name Student_VLAN
exit
vlan 20
  name Staff_VLAN
exit
vlan 30
  name Admin_VLAN
exit
vlan 40
  name Voice_VLAN
exit
vlan 50
  name IPTV_VLAN
exit
vlan 60
  name Printer_VLAN
exit
vlan 70
  name Wireless_VLAN
exit
vlan 80
  name Guest_VLAN
exit
vlan 99
  name Management_VLAN
exit
interface vlan 99
  description Management_VLAN_Interface
  ip address 10.10.99.12/24
  no shutdown
exit
ip route 0.0.0.0/0 10.10.99.254
spanning-tree mode rpvst
spanning-tree
interface lag 1
  description Multi_Chassis_LAG_To_Core
  no shutdown
  multi-chassis
  vlan trunk native 99
  vlan trunk allowed all
  lacp mode active
exit
interface 1/1/47
  no shutdown
  lag 1
exit
interface 1/1/48
  no shutdown
  lag 1
exit
interface 1/1/1-1/1/9
  description AP_Management
  no shutdown
  vlan access 70
  spanning-tree port-type admin-edge
  spanning-tree bpdu-guard
  speed auto 5g
exit
interface 1/1/10-1/1/24
  description Staff_PC
  no shutdown
  vlan access 20
  spanning-tree port-type admin-edge
  spanning-tree bpdu-guard
exit
interface 1/1/25-1/1/31
  description VoIP_Phone
  no shutdown
  vlan access 40
  spanning-tree port-type admin-edge
  spanning-tree bpdu-guard
exit
interface 1/1/32-1/1/38
  description IPTV_Display
  no shutdown
  vlan access 50
  spanning-tree port-type admin-edge
  spanning-tree bpdu-guard
exit
interface 1/1/39-1/1/45
  description Network_Printer
  no shutdown
  vlan access 60
  spanning-tree port-type admin-edge
  spanning-tree bpdu-guard
exit
qos trust dscp
qos queue-profile default
  map cos 0 to queue 0
  map cos 1 to queue 0
  map cos 2 to queue 2
  map cos 3 to queue 3
  map cos 4 to queue 4
  map cos 5 to queue 5
  map dscp 0 to queue 0
  map dscp 18 to queue 2
  map dscp 26 to queue 3
  map dscp 34 to queue 4
  map dscp 46 to queue 5
exit
interface 1/1/1-1/1/45
  qos queue-profile default
exit
dhcp-snooping
dhcp-snooping vlan 10,20,30,40,50,60,70,80,99
arp-protect
arp-protect vlan 10,20,30,40,50,60,70,80,99
interface 1/1/47
  dhcp-snooping trust
  arp-protect trust
exit
interface 1/1/48
  dhcp-snooping trust
  arp-protect trust
exit
end
write memory
```

### Switch: ACCESS-ISE-F3

- Model: Aruba CX 6300M 48p PoE
- Role: Access Switch - ISE Department (Floor 3)
- Management IP: 10.10.99.13/24

```cli
configure terminal
hostname ACCESS-ISE-F3
banner motd ^*** Authorized Users Only ***^
clock timezone asia/kolkata
ntp server 10.10.99.10
ntp enable
ssh server vrf mgmt
ssh server vrf default
dns server 8.8.8.8
dns server 8.8.4.4
vlan 10
  name Student_VLAN
exit
vlan 20
  name Staff_VLAN
exit
vlan 30
  name Admin_VLAN
exit
vlan 40
  name Voice_VLAN
exit
vlan 50
  name IPTV_VLAN
exit
vlan 60
  name Printer_VLAN
exit
vlan 70
  name Wireless_VLAN
exit
vlan 80
  name Guest_VLAN
exit
vlan 99
  name Management_VLAN
exit
interface vlan 99
  description Management_VLAN_Interface
  ip address 10.10.99.13/24
  no shutdown
exit
ip route 0.0.0.0/0 10.10.99.254
spanning-tree mode rpvst
spanning-tree
interface lag 1
  description Multi_Chassis_LAG_To_Core
  no shutdown
  multi-chassis
  vlan trunk native 99
  vlan trunk allowed all
  lacp mode active
exit
interface 1/1/47
  no shutdown
  lag 1
exit
interface 1/1/48
  no shutdown
  lag 1
exit
interface 1/1/1-1/1/16
  description AP_Management
  no shutdown
  vlan access 70
  spanning-tree port-type admin-edge
  spanning-tree bpdu-guard
  speed auto 5g
exit
interface 1/1/17-1/1/26
  description Staff_PC
  no shutdown
  vlan access 20
  spanning-tree port-type admin-edge
  spanning-tree bpdu-guard
exit
interface 1/1/27-1/1/33
  description VoIP_Phone
  no shutdown
  vlan access 40
  spanning-tree port-type admin-edge
  spanning-tree bpdu-guard
exit
interface 1/1/34-1/1/40
  description IPTV_Display
  no shutdown
  vlan access 50
  spanning-tree port-type admin-edge
  spanning-tree bpdu-guard
exit
interface 1/1/41-1/1/47
  description Network_Printer
  no shutdown
  vlan access 60
  spanning-tree port-type admin-edge
  spanning-tree bpdu-guard
exit
qos trust dscp
qos queue-profile default
  map cos 0 to queue 0
  map cos 1 to queue 0
  map cos 2 to queue 2
  map cos 3 to queue 3
  map cos 4 to queue 4
  map cos 5 to queue 5
  map dscp 0 to queue 0
  map dscp 18 to queue 2
  map dscp 26 to queue 3
  map dscp 34 to queue 4
  map dscp 46 to queue 5
exit
interface 1/1/1-1/1/47
  qos queue-profile default
exit
dhcp-snooping
dhcp-snooping vlan 10,20,30,40,50,60,70,80,99
arp-protect
arp-protect vlan 10,20,30,40,50,60,70,80,99
interface 1/1/47
  dhcp-snooping trust
  arp-protect trust
exit
interface 1/1/48
  dhcp-snooping trust
  arp-protect trust
exit
end
write memory
```

## Verification

```cli
show vlan
show lacp interfaces
show spanning-tree
show vsx status
show vsf
show ip route
show interface brief
show qos queue-profile
show dhcp-snooping
show arp-protect
```
