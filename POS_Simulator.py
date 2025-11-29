import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime
import json
import os

# --- THEME CONSTANTS ---
COL_BG_MAIN = "#F4F6F9"       
COL_CARD = "#FFFFFF"          
COL_TEXT = "#2C3E50"          
COL_HEADER_TXT = "#00ACC1"    

COL_SALE = "#43A047"          
COL_VOID = "#FB8C00"          
COL_SETTLE = "#1E88E5"        
COL_REFUND = "#D81B60"        
COL_CANCEL = "#E53935"        
COL_CONN = "#546E7A"          
COL_RECEIPT_BG = "#FFF8E1"    # Light Yellow for Receipt

# Fonts
FONT_HEADER = ("Segoe UI", 16, "bold")
FONT_LABEL = ("Segoe UI", 9, "bold")
FONT_INPUT = ("Consolas", 12)
FONT_BTN = ("Segoe UI", 10, "bold")
FONT_LOG = ("Consolas", 9)
FONT_RECEIPT = ("Courier New", 10)

# Constants
STX = b'\x02'
ETX = b'\x03'
CONFIG_FILE = "simulator_config.json"

# --- HELPER: TOAST NOTIFICATION ---
class ToastNotification(tk.Toplevel):
    def __init__(self, parent, message, duration=3000, color="#333333"):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        label = tk.Label(self, text=message, bg=color, fg="#FFFFFF", 
                         font=("Segoe UI", 11), padx=20, pady=10)
        label.pack()
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_rooty() + parent.winfo_height() - 120
        self.geometry(f"+{x}+{y}")
        self.after(duration, self.destroy)

# --- HELPER: DIGITAL RECEIPT POPUP ---
class ReceiptPopup(tk.Toplevel):
    def __init__(self, parent, data_dict):
        super().__init__(parent)
        self.title("Transaction Receipt")
        self.geometry("300x400")
        self.configure(bg=COL_RECEIPT_BG)
        self.attributes("-topmost", True)
        
        # Center Screen
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - 150
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - 200
        self.geometry(f"+{x}+{y}")

        # UI
        lbl_title = tk.Label(self, text="*** APPROVED ***", bg=COL_RECEIPT_BG, fg="black", font=("Courier New", 14, "bold"))
        lbl_title.pack(pady=(20, 10))
        
        txt = f"""
MERCHANT: GHL SIMULATOR
TIME: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

TRANS TYPE: {data_dict.get('type', 'SALE')}
INVOICE NO: {data_dict.get('invoice', '000000')}
CARD NO:    {data_dict.get('card', 'XXXX')}
AUTH CODE:  {data_dict.get('auth', '000000')}

------------------------------
TOTAL:      RM {data_dict.get('amount', '0.00')}
------------------------------

      THANK YOU!
"""
        lbl_info = tk.Label(self, text=txt, bg=COL_RECEIPT_BG, fg="black", font=FONT_RECEIPT, justify="left")
        lbl_info.pack(padx=20, pady=5)
        
        btn = ttk.Button(self, text="CLOSE", command=self.destroy)
        btn.pack(pady=20)

# --- CUSTOM WIDGET: ATM INPUT ---
class CurrencyEntry(tk.Entry):
    def __init__(self, master=None, **kwargs):
        self.var = tk.StringVar()
        kwargs['textvariable'] = self.var
        super().__init__(master, **kwargs)
        self.raw_value = 0
        self.var.set("0.00")
        self.bind("<Key>", self.handle_keypress)
        self.bind("<BackSpace>", self.handle_backspace)

    def handle_keypress(self, event):
        if event.char.isdigit():
            if len(str(self.raw_value)) < 10: 
                self.raw_value = self.raw_value * 10 + int(event.char)
                self.update_display()
        return "break"

    def handle_backspace(self, event):
        self.raw_value = self.raw_value // 10
        self.update_display()
        return "break"

    def update_display(self):
        self.var.set("{:.2f}".format(self.raw_value / 100))

    def get_amount(self):
        return self.raw_value / 100.0

    def set_amount(self, float_val):
        self.raw_value = int(float_val * 100)
        self.update_display()

# --- BACKEND LOGIC ---
class GHLProtocol:
    def __init__(self):
        self.ser = None
        self.stop_flag = False

    def connect(self, port):
        # Safety Close first to prevent PermissionError
        self.disconnect()
        time.sleep(0.1) # Brief pause to let Windows release the handle
        
        try:
            self.ser = serial.Serial(
                port=port, baudrate=9600, bytesize=8,
                parity='N', stopbits=1, timeout=1
            )
            return True, f"Connected to {port}"
        except Exception as e:
            return False, str(e)

    def disconnect(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except:
            pass # Ignore errors during disconnect

    def cancel_wait(self):
        self.stop_flag = True

    def calculate_chk(self, data):
        d = bytearray(data)
        rem = len(d) % 8
        if rem: d += b'\xFF' * (8 - rem)
        chk = bytearray(8)
        for i in range(0, len(d), 8):
            chunk = d[i:i+8]
            for j in range(8): chk[j] ^= chunk[j]
        return bytes(chk)

    def build_packet(self, cmd, amt, inv, cshr):
        payload = f"{cmd}{int(amt*100):012d}{int(inv):06d}{str(cshr):>4}".encode('ascii')
        return STX + payload + self.calculate_chk(payload) + ETX

    def send_recv(self, packet, cb):
        if not self.ser or not self.ser.is_open:
            cb("Err: Disconnected", None)
            return
        self.stop_flag = False
        
        def t():
            try:
                cb(f"TX > {packet.hex().upper()}", None)
                self.ser.write(packet)
                buff = bytearray()
                start = time.time()
                while True:
                    if self.stop_flag: 
                        cb("User Cancelled (Software Side)", None); return
                    if time.time() - start > 60: 
                        cb("Err: Timeout", None); return
                    
                    b = self.ser.read(1)
                    if b:
                        buff.extend(b)
                        if b == ETX:
                            cb(f"RX < {buff.hex().upper()}", bytes(buff))
                            return
            except Exception as e:
                cb(f"Err: {e}", None)
        threading.Thread(target=t, daemon=True).start()

# --- GUI ---
class POSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GHL Terminal Simulator // DEADBOY v7")
        self.root.geometry("900x750")
        self.root.configure(bg=COL_BG_MAIN)
        self.proto = GHLProtocol()
        
        self.setup_styles()
        self.build_layout()
        self.load_settings() # Load saved data

        # Ensure port closes on exit
        import atexit
        atexit.register(self.proto.disconnect)

    def setup_styles(self):
        s = ttk.Style()
        s.theme_use('clam')
        s.configure("Card.TFrame", background=COL_CARD, relief="flat", borderwidth=0)
        s.configure("Main.TFrame", background=COL_BG_MAIN)
        s.configure("Header.TLabel", background=COL_CARD, foreground=COL_HEADER_TXT, font=FONT_HEADER)
        s.configure("Std.TLabel", background=COL_CARD, foreground=COL_TEXT, font=FONT_LABEL)
        s.configure("TEntry", fieldbackground="#F0F0F0", foreground="black", borderwidth=1, relief="solid")
        s.configure("TCheckbutton", background=COL_CARD, foreground=COL_TEXT, font=("Segoe UI", 9))
        
        def cfg_btn(name, bg):
            s.configure(name, background=bg, foreground="white", font=FONT_BTN, borderwidth=0)
            s.map(name, background=[('active', '#90A4AE'), ('disabled', '#CFD8DC')])

        cfg_btn("Sale.TButton", COL_SALE)
        cfg_btn("Void.TButton", COL_VOID)
        cfg_btn("Settle.TButton", COL_SETTLE)
        cfg_btn("Refund.TButton", COL_REFUND)
        cfg_btn("Cancel.TButton", COL_CANCEL)
        cfg_btn("Conn.TButton", COL_CONN)
        s.configure("Small.TButton", background="#ECEFF1", foreground="#455A64", font=("Segoe UI", 8))

    def build_layout(self):
        # --- HEADER ---
        header = ttk.Frame(self.root, style="Card.TFrame", padding=(20, 15))
        header.pack(fill="x", side="top")
        ttk.Label(header, text="POS - Terminal Simulator", style="Header.TLabel").pack(side="left")
        
        conn_box = ttk.Frame(header, style="Card.TFrame")
        conn_box.pack(side="right")
        
        self.cv_status = tk.Canvas(conn_box, width=15, height=15, bg=COL_CARD, highlightthickness=0)
        self.status_dot = self.cv_status.create_oval(2, 2, 13, 13, fill="#B0BEC5", outline="")
        self.cv_status.pack(side="left", padx=5)

        ports = [p.device for p in serial.tools.list_ports.comports()] or ["COM1"]
        self.port_var = tk.StringVar(value=ports[0])
        self.cb_port = ttk.Combobox(conn_box, textvariable=self.port_var, values=ports, width=10, state="readonly")
        self.cb_port.pack(side="left", padx=5)
        self.btn_conn = ttk.Button(conn_box, text="CONNECT", style="Conn.TButton", width=12, command=self.toggle_conn)
        self.btn_conn.pack(side="left")

        # --- BODY ---
        container = ttk.Frame(self.root, style="Main.TFrame", padding=20)
        container.pack(fill="both", expand=True)
        card = ttk.Frame(container, style="Card.TFrame", padding=25)
        card.pack(fill="both", expand=True)

        # 1. Inputs
        input_grid = ttk.Frame(card, style="Card.TFrame")
        input_grid.pack(fill="x", pady=(0, 15))
        input_grid.columnconfigure(1, weight=1); input_grid.columnconfigure(3, weight=1)

        # Amount
        ttk.Label(input_grid, text="AMOUNT (RM)", style="Std.TLabel").grid(row=0, column=0, sticky="e", padx=10)
        self.ent_amt = CurrencyEntry(input_grid, font=FONT_INPUT, width=15, justify="right")
        self.ent_amt.set_amount(1.00)
        self.ent_amt.grid(row=0, column=1, sticky="ew", padx=10)
        
        qf = ttk.Frame(input_grid, style="Card.TFrame")
        qf.grid(row=1, column=1, sticky="w", padx=10, pady=(2, 0))
        for amt in [1, 5, 10, 50]:
            ttk.Button(qf, text=f"{amt}", style="Small.TButton", width=4,
                       command=lambda a=amt: self.ent_amt.set_amount(a)).pack(side="left", padx=1)

        # Invoice
        ttk.Label(input_grid, text="INVOICE NO.", style="Std.TLabel").grid(row=0, column=2, sticky="e", padx=10)
        self.ent_inv = ttk.Entry(input_grid, font=FONT_INPUT, width=15, justify="right")
        self.ent_inv.insert(0, "000001")
        self.ent_inv.grid(row=0, column=3, sticky="ew", padx=10)

        # Auto Increment Checkbox
        self.var_autoincrement = tk.BooleanVar(value=True)
        ttk.Checkbutton(input_grid, text="Auto-Increment on Success", variable=self.var_autoincrement, 
                        style="TCheckbutton").grid(row=1, column=3, sticky="w", padx=10)

        # Cashier
        ttk.Label(input_grid, text="CASHIER ID", style="Std.TLabel").grid(row=2, column=0, sticky="e", padx=10, pady=(15,0))
        self.ent_csh = ttk.Entry(input_grid, font=FONT_INPUT, width=15, justify="right")
        self.ent_csh.insert(0, "99")
        self.ent_csh.grid(row=2, column=1, sticky="ew", padx=10, pady=(15,0))

        ttk.Separator(card, orient="horizontal").pack(fill="x", pady=20)

        # 2. Buttons
        btn_grid = ttk.Frame(card, style="Card.TFrame")
        btn_grid.pack(fill="x", pady=5)
        btn_grid.columnconfigure((0,1), weight=1)

        ttk.Button(btn_grid, text="SALE", style="Sale.TButton", padding=15,
                   command=lambda: self.tx("020")).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ttk.Button(btn_grid, text="VOID", style="Void.TButton", padding=15,
                   command=lambda: self.tx("022")).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(btn_grid, text="SETTLEMENT", style="Settle.TButton", padding=15,
                   command=lambda: self.tx("050")).grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        ttk.Button(btn_grid, text="REFUND", style="Refund.TButton", padding=15,
                   command=lambda: self.tx("026")).grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        self.btn_cancel = ttk.Button(card, text="STOP WAITING (SOFTWARE RESET)", style="Cancel.TButton", 
                                     state="disabled", padding=10, command=self.stop_wait)
        self.btn_cancel.pack(fill="x", pady=(15, 10), padx=5)

        # 3. Logs
        log_lbl = ttk.Frame(card, style="Card.TFrame")
        log_lbl.pack(fill="x", pady=(10, 5))
        ttk.Label(log_lbl, text="COMMUNICATION LOG", style="Std.TLabel").pack(side="left", padx=5)
        
        tools = ttk.Frame(log_lbl, style="Card.TFrame")
        tools.pack(side="right")
        ttk.Button(tools, text="COPY", style="Small.TButton", width=8, command=self.copy_log).pack(side="left", padx=2)
        ttk.Button(tools, text="SAVE", style="Small.TButton", width=8, command=self.save_log).pack(side="left", padx=2)
        ttk.Button(tools, text="CLEAR", style="Small.TButton", width=8, command=self.clr_log).pack(side="left", padx=2)

        self.log_box = scrolledtext.ScrolledText(card, height=8, font=FONT_LOG, 
                                                 bg="#263238", fg="#ECEFF1", bd=0, state="disabled")
        self.log_box.pack(fill="both", expand=True, padx=5, pady=5)
        self.log_box.tag_config("tx", foreground="#4FC3F7")
        self.log_box.tag_config("rx", foreground="#69F0AE")
        self.log_box.tag_config("err", foreground="#FF8A80")

    # --- SAVE/LOAD SETTINGS ---
    def save_settings(self):
        data = {
            "port": self.port_var.get(),
            "invoice": self.ent_inv.get(),
            "cashier": self.ent_csh.get(),
            "auto_inc": self.var_autoincrement.get()
        }
        try:
            with open(CONFIG_FILE, "w") as f: json.dump(data, f)
        except: pass

    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f: data = json.load(f)
                if "port" in data: self.port_var.set(data["port"])
                if "invoice" in data: 
                    self.ent_inv.delete(0, tk.END)
                    self.ent_inv.insert(0, data["invoice"])
                if "cashier" in data:
                    self.ent_csh.delete(0, tk.END)
                    self.ent_csh.insert(0, data["cashier"])
                if "auto_inc" in data:
                    self.var_autoincrement.set(data["auto_inc"])
            except: pass

    # --- ACTIONS ---
    def show_toast(self, message, color="#333333"):
        ToastNotification(self.root, message, color=color)

    def show_receipt(self, data):
        # Extract meaningful data from raw payload
        # Spec 4.2: Payload = Cmd(3)+Err(2)+Card(22)+Exp(4)+Type(2)+Auth(8)+Amt(12)...
        # Note: Indexing here is approximate based on fixed width.
        try:
            payload = data[1:-9] # Strip framing
            if len(payload) < 50: return # Too short
            
            d_dict = {
                "type": "SALE", # Default
                "card": payload[5:27].decode(errors='ignore').strip(),
                "auth": payload[33:41].decode(errors='ignore').strip(),
                "amount": "{:.2f}".format(int(payload[41:53]) / 100)
            }
            # Invoice is further down, roughly index 65, length 6
            if len(payload) > 70:
                d_dict['invoice'] = payload[65:71].decode(errors='ignore')

            ReceiptPopup(self.root, d_dict)
        except: pass

    def log(self, msg, tag=None):
        ts = datetime.now().strftime("[%H:%M:%S] ")
        self.log_box.config(state="normal")
        self.log_box.insert("end", ts + msg + "\n", tag)
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def copy_log(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log_box.get("1.0", tk.END))
        self.show_toast("Log copied!")

    def save_log(self):
        data = self.log_box.get("1.0", tk.END)
        f = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if f:
            with open(f, "w") as file: file.write(data)
            self.show_toast(f"Saved to {f}")

    def clr_log(self):
        self.log_box.config(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.config(state="disabled")

    def toggle_conn(self):
        if "CONNECT" in self.btn_conn['text']:
            ok, msg = self.proto.connect(self.port_var.get())
            if ok:
                self.log(f"[{msg}]")
                self.btn_conn.config(text="DISCONNECT", style="Cancel.TButton")
                self.cb_port.config(state="disabled")
                self.cv_status.itemconfig(self.status_dot, fill="#00C853")
                self.save_settings() # Save on connect
            else:
                self.log(f"Fail: {msg}", "err")
                messagebox.showerror("Error", msg)
        else:
            self.proto.disconnect()
            self.log("[Disconnected]")
            self.btn_conn.config(text="CONNECT", style="Conn.TButton")
            self.cb_port.config(state="readonly")
            self.cv_status.itemconfig(self.status_dot, fill="#B0BEC5")

    def stop_wait(self):
        self.proto.cancel_wait()
        self.log(">>> STOP SIGNAL SENT <<<", "err")

    def tx(self, cmd):
        if not self.proto.ser or not self.proto.ser.is_open:
            messagebox.showwarning("Error", "Connect port first.")
            return
        
        try:
            amt = 0.0 if cmd in ["050", "022"] else self.ent_amt.get_amount()
            inv = 0 if cmd in ["020", "050"] else int(self.ent_inv.get())
            cshr = self.ent_csh.get()
            
            pkt = self.proto.build_packet(cmd, amt, inv, cshr)
            
            self.btn_cancel.config(state="normal")
            
            if cmd == "020": self.show_toast("Please SWIPE/INSERT CARD on Terminal", COL_SALE)
            elif cmd == "026": self.show_toast("Refund Mode Active", COL_REFUND)
            elif cmd == "050": self.show_toast("Settlement In Progress...", COL_SETTLE)
            
            self.save_settings() # Save invoice/cashier before sending
            self.proto.send_recv(pkt, self.on_resp)
        except ValueError:
            messagebox.showerror("Error", "Check inputs.")

    def on_resp(self, msg, data):
        def update():
            self.btn_cancel.config(state="disabled")
            tag = "tx" if "TX" in msg else ("err" if "Err" in msg else "rx")
            self.log(msg, tag)
            
            if data and len(data) > 10:
                try:
                    payload = data[1:-9]
                    err = payload[3:5].decode(errors='ignore')
                    
                    if err == "00":
                        self.show_toast("TRANSACTION APPROVED", COL_SALE)
                        # Show Digital Receipt
                        self.show_receipt(data)
                        
                        # Auto Increment
                        if self.var_autoincrement.get():
                            curr = int(self.ent_inv.get())
                            self.ent_inv.delete(0, tk.END)
                            self.ent_inv.insert(0, f"{curr + 1:06d}")
                    else:
                        self.show_toast(f"DECLINED: {err}", COL_CANCEL)
                except: pass
        self.root.after(0, update)

if __name__ == "__main__":
    root = tk.Tk()
    app = POSApp(root)
    root.mainloop()