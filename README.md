# GHL Terminal Simulator // DEADBOY

## Overview
This software simulates the behavior of a GHL/Verifone payment terminal via RS232. It is designed to help developers and IT professionals test their Point of Sale (POS) integration without needing to perform live transactions. It implements the specific packet structure, check digit algorithms, and handshake protocols defined in the **POS Integration v1017** specification.

## 🎥 See it in Action

https://github.com/user-attachments/assets/5b59c053-6600-4861-b0ac-29dbba90bf32

<!-- VIDEO PLACEHOLDER START -->
<!-- Drag and drop your MP4/MOV file here, or paste your YouTube/GIF link below -->

<!-- VIDEO PLACEHOLDER END -->

## 📂 Included Files
* **`GHL_Terminal_Simulator_Deadboy_v7_Final.exe`** - The main standalone application (Python build).
* **`GHL_Simulator_Deadboy` (Folder)** - Complete C# Source Code (Visual Studio Project).
* **`pos_gui_v7.py`** - Python Source Code.
* [cite_start]**`POS Integration v1017.pdf`** - Official protocol documentation[cite: 151].
* [cite_start]**`PAXL920BE_T568b To Db9 Rs232 Documentation.pdf`** - Wiring guide for the custom cable[cite: 1].
* [cite_start]**`a920_guide.pdf`** - User guide for the PAX A920 terminal[cite: 1774].

---

## 🛠 Hardware Setup & Requirements

To successfully use this simulator or the physical terminal with a PC, you must replicate the following hardware setup:

### 1. Required Hardware
* **PAX A920 Terminal**
* **PAX L920-BE Base Station** (Docking Station)
* **USB to RS232 Adapter**
    * ⚠️ **IMPORTANT:** You must use an adapter with the **Prolific PL2303 Chipset**.
    * *Note: FTDI chipsets are known to have compatibility issues with this specific setup.*

### 2. Base Station Setup (L920-BE)
The L920-BE base acts as the communication bridge.
1.  **Power:** Connect power via the Micro-USB port on the base.
2.  **Internet:** Connect an Ethernet cable to the Network (LAN) port on the base.
    * *The base creates its own local WiFi hotspot.*
3.  **PC Connection:** Connect your RS232 Cable to the RS232 port on the base.

### 3. Terminal Connection (A920)
1.  Place the A920 terminal onto the L920-BE base.
2.  Ensure the **Pogo Pins** make contact; this handles both charging and data communication.
3.  **Connectivity:**
    * The terminal connects to the Base Station via Bluetooth or the Base's WiFi.
    * ⚠️ **CRITICAL WIFI NOTE:** The WiFi SSID broadcasted by the base **MUST have a password**. The PAX A920 will **not** detect or connect to "Open" (no password) networks created by the base or any other router/access point.

---

## 🔌 Wiring Guide: RS232 to RJ45
The L920-BE base uses an RJ45 port for Serial communication, requiring a custom cable to convert it to a standard DB9 PC Serial connection.

[cite_start]Please refer to **`PAXL920BE_T568b To Db9 Rs232 Documentation.pdf`** for the schematic[cite: 1].

**Standard: T568B**
* [cite_start]**RJ45 Pin 7 (White/Brown)** -> **DB9 Pin 1 (DCD)** [cite: 38]
* [cite_start]**RJ45 Pin 5 (White/Blue)** -> **DB9 Pin 3 (TXD)** [cite: 35]
* [cite_start]**RJ45 Pin 6 (Green)** -> **DB9 Pin 4 (DTR)** [cite: 36]
* [cite_start]*(Refer to the PDF for the complete pinout map)*[cite: 41].

---

## 💻 Developer Integration Guide

If you are integrating this logic into your own POS software (Sentec PMS, etc.), use the following protocol details.

### Protocol Basics
* **Baud Rate:** 9600
* **Data Bits:** 8
* **Parity:** None
* **Stop Bits:** 1
* **Flow Control:** None

### Packet Structure
[cite_start]Every message sent to the terminal follows this strict format[cite: 390]:
`[STX] [PAYLOAD] [CHECK DIGIT] [ETX]`

### Sample Payload Breakdown
**Scenario:**
* **Transaction:** SALE
* **Amount:** RM 1.20
* **Invoice Number:** 123456
* **Cashier ID:** 99

**1. Constructing the Payload:**
* **Command (3 bytes):** `020` (Sale)
* **Amount (12 bytes):** `000000000120` (Implied decimal, so 120 = 1.20)
* **Invoice (6 bytes):** `123456`
* **Cashier (4 bytes):** `  99` (Right-justified, padded with spaces)

**Raw Payload String (25 bytes):**
`020000000000120123456  99`

**2. Calculating Check Digit (XOR):**
The protocol requires breaking the payload into **8-byte blocks** and performing an XOR operation on them. [cite_start]If the last block is shorter than 8 bytes, pad it with `0xFF` [cite: 437-440].

* Block 1: `02000000`
* Block 2: `00001201`
* Block 3: `23456  9`
* Block 4: `9` + (7 bytes of `0xFF`)

**Result:** `Block1 ^ Block2 ^ Block3 ^ Block4` = **8-Byte Check Digit**

---

## 🚀 How to Use the Simulator
1.  Connect your Prolific RS232 cable to the PC.
2.  Open **Device Manager** -> **Ports (COM & LPT)** and note the COM Port number (e.g., COM1).
3.  Run **`GHL_Terminal_Simulator_Deadboy_v7_Final.exe`**.
4.  Select your COM port from the dropdown and click **CONNECT**.
5.  Enter Amount and Invoice Number (or leave defaults).
6.  Click **SALE**.
7.  The log will show the raw TX (Transmit) and RX (Receive) hex data for debugging.

---
**Developed by Deadboy** | Based on GHL/Verifone Integration Spec v1.0.17
