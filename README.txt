PROJECT: GHL Terminal Simulator // DEADBOY
VERSION: 10.0 (C# / WinForms)
AUTHOR: Kesh / Deadboy Dev

---------------------------------------------------------------------
1. OVERVIEW
---------------------------------------------------------------------
This project simulates the behavior of a GHL/Verifone terminal via RS232.
It implements the specific packet structure, 8-byte XOR check digit, 
and handshake protocol defined in the "POS Integration v1017" spec.

---------------------------------------------------------------------
2. REQUIREMENTS
---------------------------------------------------------------------
- IDE: Visual Studio 2022 (Community or Professional)
- Framework: .NET 6.0, 7.0, or 8.0 (Windows Forms App)
- Dependencies: 
  You MUST install the following NuGet package to handle COM ports:
  > Install-Package System.IO.Ports

---------------------------------------------------------------------
3. INTEGRATION GUIDE (FOR DEVELOPERS)
---------------------------------------------------------------------
The core communication logic is isolated in "GHLProtocol.cs".
You do not need the GUI code to use this in your own POS.

To integrate:
1. Copy "GHLProtocol.cs" into your project.
2. Ensure you have the "System.IO.Ports" package installed.
3. Instantiate and use the class as follows:

   // Initialize
   GHLProtocol terminal = new GHLProtocol();
   string status = terminal.Connect("COM1");

   if (status == "Success") 
   {
       // Create Packet (Command, Amount, Invoice, CashierID)
       // Cmd: "020" (Sale), "022" (Void), "050" (Settle), "026" (Refund)
       byte[] packet = terminal.BuildPacket("020", 1.00, 0, "99");

       // Send & Wait for Response (Async)
       await terminal.SendAndReceive(packet, (logMsg, rawData) => 
       {
           // 'logMsg' contains "TX > ..." or "RX < ..." strings for logging
           // 'rawData' contains the byte array returned by the terminal
           
           if (rawData != null)
           {
               // Parse response (Remove STX/ETX/CheckDigit)
               string payload = Encoding.ASCII.GetString(rawData, 1, rawData.Length - 10);
               string errCode = payload.Substring(3, 2); 
               
               if (errCode == "00") Console.WriteLine("Transaction Approved");
               else Console.WriteLine("Declined: " + errCode);
           }
       });
   }

---------------------------------------------------------------------
4. HOW TO BUILD THE SIMULATOR GUI (SINGLE FILE EXE)
---------------------------------------------------------------------
If you want to rebuild the GUI tool as a standalone .exe:

1. Open the solution in Visual Studio.
2. Open the "Developer PowerShell" (View > Terminal).
3. Run this command to produce a single, portable file:

   dotnet publish -c Release -r win-x64 --self-contained -p:PublishSingleFile=true -o ".\Publish"

4. The output EXE will be in the "Publish" folder.

---------------------------------------------------------------------