# -*- coding: utf-8 -*-
import subprocess
import logging
from src.services.servicenow.odbc.odbc import ServerOdbc
import json
import requests
from src.services.cyberark.cyberark import cyberark
from time import sleep
import re
import paramiko
import os
from email.message import EmailMessage
import smtplib

MAIL_RELAY = "mailrelay.sandisk.com"
MAIL_PORT = 25
DEFAULT_RECEIVER = "vigneswaran.murthy@sandisk.com" 
 
# LOGGING SETUP
# =========================================
logging.basicConfig(
    filename="/data/automation/os_config/logs/monitor.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
 
logging.info("Script started")
 
def send_email(subject: str, body: str, receiver_email: str = DEFAULT_RECEIVER) -> None:
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = "noreply@sandisk.com"
        msg["To"] = "vigneswaran.murthy@sandisk.com"
        msg.set_content(body)
 
        with smtplib.SMTP(MAIL_RELAY, MAIL_PORT, timeout=30) as server:
            server.send_message(msg)
            logging.info("Email sent to %s: %s", receiver_email, subject)
    except Exception as e:
        logging.exception("Failed to send email to %s: %s", receiver_email, e)
 
 
def ubuntu_os_config(new_server_entry:str):
    # === FILE AND SCRIPT PATHS ===
    os.chdir("/data/automation/os_config/ubuntu_os_config")
    server_file = "/data/automation/os_config/ubuntu_os_config/servers.txt"
    setup_script = "/data/automation/os_config/ubuntu_os_config/setup_keys.sh"
    config_script = "/data/automation/os_config/ubuntu_os_config/standard_os_config.sh"
    try:
        # --- 1. Update server.txt for new hostname ---
        logging.info("Updating server.txt for %s", new_server_entry)
        update_cmd = f"echo '{new_server_entry.strip()}' | sudo tee {server_file}"
        result = subprocess.run(update_cmd, shell=True, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            logging.error("Failed to update server.txt: %s", (result.stderr or result.stdout))
            return (result.stderr or result.stdout) or "Failed to update server.txt"
 
        # --- 2. Run setup_keys.sh to copy the root key to new server ---
        result = subprocess.run(f"bash {setup_script}", shell=True, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            logging.error("setup_keys.sh failed: %s", (result.stderr or result.stdout))
            return (result.stderr or result.stdout) or "setup_keys.sh failed"
 
        # --- 3. OS configureation script running on the new server  ---
        result = subprocess.run(f"bash {config_script}", shell=True, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            logging.error("standard_os_config.sh failed: %s", (result.stderr or result.stdout))
            #return (result.stderr or result.stdout) or "standard_os_config.sh failed"    
 
        # --- 4️. Display the file contents at the end ---
        new_hostname = new_server_entry.strip()
        output_file = "/data/automation/os_config/ubuntu_os_config/provisioning.log"
        cat_out = subprocess.run(f"cat {output_file}", shell=True, text=True, capture_output=True)
        print(cat_out.stdout)
 
    except Exception as e:
        print(f" Error: {e}")
    return cat_out.stdout
 
def redhat_os_config(new_server_entry:str):
    os.chdir("/data/automation/os_config/redhat_os_config")
 
    # === FILE AND SCRIPT PATHS ===
    server_file = "/data/automation/os_config/redhat_os_config/servers.txt"
    setup_script = "/data/automation/os_config/redhat_os_config/setup_keys.sh"
    config_script = "ansible-playbook -i server.txt main.yml"
    ansible_cmd = ["ansible-playbook", "-i", server_file, "main.yml"]
 
    try:
        print("Step 1: Updating server.txt")
        update_cmd = ["bash", "-c", f"echo '{new_server_entry.strip()}' | sudo tee {server_file}"]
        result = subprocess.run(update_cmd, text=True, capture_output=True)
        if result.returncode != 0:
            logging.error("Failed to update server.txt: %s", (result.stderr or result.stdout))
            return (result.stderr or result.stdout) or "Failed to update server.txt"
   
        print("Step 2: Running setup_keys.sh")
        result = subprocess.run(["bash", setup_script], text=True, capture_output=True)
        if result.returncode != 0:
            logging.error("setup_keys.sh failed: %s", (result.stderr or result.stdout))
            return (result.stderr or result.stdout) or "setup_keys.sh failed"
   
        print("Step 3: Running Ansible playbook")
        result = subprocess.run(ansible_cmd, text=True, capture_output=True)
        if result.returncode != 0:
            logging.error("ansible-playbook failed: %s", (result.stderr or result.stdout))
            #return (result.stderr or result.stdout) or "ansible-playbook failed"
 
        # --- 4️. Display the file contents at the end ---
        new_hostname = new_server_entry.strip()
        output_file = "/data/automation/os_config/redhat_os_config/ansible_output/"+new_hostname+"/status.txt"
        cat_out = subprocess.run(f"cat {output_file}", shell=True, text=True, capture_output=True)
        print(cat_out.stdout)
 
    except Exception as e:
        print(f" Error: {e}")
    return cat_out.stdout
 
# def task_close(ticket_number,comment):
def task_close(ticket_number,comment,stat, assign_to, work_comments=None,close_comments=None,sol=None,):
    url = 'https://sndk.service-now.com/api/now/table/u_rpa_tool_task_load'
    username = 'RPA_Tool'
    cb = cyberark(username)
    auth = cb.get_cyberark_object()
    auth = auth['basic auth']
    headers = {
        'Content-Type':'application/json',
        'Accept':'application/json',
        'Authorization': auth
    }
    data = json.dumps({
    'u_number': ticket_number,
    'u_comments': comment,
    'u_work_notes': work_comments,
    'u_close_notes': close_comments,
    'u_solution': sol,
    'u_assigned_to':assign_to,
    'u_state': stat
    })
    logging.info(f"Closing task {ticket_number} with comment: {comment}")
    resp = requests.post( url=url, headers=headers, data=data, verify = False )
    logging.info(f"Response status: {resp.status_code}, Response: {resp.text}")
 
# def task_update(ticket_number,comment):
def task_update(val, comments, stat, assign_to, work_comments):
    url = 'https://sndk.service-now.com/api/now/table/u_rpa_tool_task_load'
    username = 'RPA_Tool'
    cb = cyberark(username)
    auth = cb.get_cyberark_object()
    auth = auth['basic auth']
    headers = {
        'Content-Type':'application/json',
        'Accept':'application/json',
        'Authorization': auth
    }
    data = json.dumps({
    'u_number': val,
    'comments': comments,
    'u_work_notes': work_comments,
    'u_assigned_to':assign_to,
    'u_state': stat
    })
    logging.info(f"Updating task {val} with comment: {comments}")
    resp = requests.post( url=url, headers=headers, data=data, verify=False)
    logging.info(f"Response status: {resp.status_code}, Response: {resp.text}")
 
 
# Extracts the request type from the description string
def extract_request_type(description):
    pattern = r'Request Type: (.*?)(?:\n|$)'
    match = re.search(pattern, description)
    if match:
        return match.group(1).strip()
    logging.warning("extract_request_type: No match found for request type.")
    return None
 
# Extracts the employee ID from the description string
def extract_employee_id(description):
    pattern = r'OS: (.*?)(?:\n|$)'
    match = re.search(pattern, description)
    if match:
        return match.group(1).strip()
    logging.warning("extract_employee_id: No match found for employee ID.")
    return None
 
os_pattern = r"OS:\s(.*?)\nMemory"
# Function to extract the value between "OS:" and "\nMemory"
def extract_os_value(text):
    match = re.search(os_pattern, text)
    if match:
        return match.group(1)  # Capture the value between "OS:" and "\nMemory"
    else:
        return "No OS value found"
 
host_pattern = r"Server Name:\s(.*?)\nLocation"
# Function to extract the value between "OS:" and "\nMemory"
def extract_host_value(text):
    match = re.search(host_pattern, text)
    if match:
        return match.group(1)  # Capture the value between "OS:" and "\nMemory"
    else:
        return "No OS value found"
 
def run_command(cmd):
    result = subprocess.run(cmd, text=True, capture_output=True)
    return result.stdout + result.stderr
 
def ping_host(hostname):
    cmd = ["ping", "-c", "2", hostname]
    out = run_command(cmd)
    ok = "TTL=" in out or "ttl=" in out
    return ok, out
 
 
def process_tickets_cycle() -> None:
    logging.info("Starting ticket processing loop.")
    try:
        open_tickets = ServerOdbc().run()
    except Exception:
        logging.exception("Failed to fetch tickets from ServerOdbc")
        return
   
    try:
        tickets_open = open_tickets.json().get("result", [])
    except Exception:
        logging.exception("Failed to parse ServerOdbc response JSON")
        return
    logging.info("Found %d open tickets", len(tickets_open))
    tic_data = {}
    for tic in tickets_open:
        try:
            ticket_num = tic.get('number')
            desc = tic.get('description', '')
            os_type = extract_os_value(desc)
            host_name = extract_host_value(desc)
            tic_data[ticket_num] = [os_type, host_name]
            logging.info("Parsed ticket %s -> os: %s host: %s", ticket_num, os_type, host_name)
        except Exception:
            logging.exception("Failed to process ticket entry: %s", tic)
    # Second pass: handle each ticket
    for val, (os_info, host) in tic_data.items():
        if not host or host.startswith("No host"):
            logging.warning("Ticket %s has no valid host; assigning to Linux Team", val)
            task_update(val, "No valid host found in ticket description", '2', 'RPA Tool', "No host found")
            continue
       
        
        ok, ping_out = ping_host(host_name)
        assign_to = 'RPA_Tool'
       
        stat_wip = '2' # Work In Progress
        stat_closed = '3' # Closed
        if not ok:
            logging.warning("Host %s not reachable for ticket %s", host_name, val)
            send_email(f"Automation Failed {val}", ping_out)
            task_update(val, ping_out, stat_wip, assign_to, ping_out)
            continue
 
 
        success = False
        output = ""
       
        if 'Red Hat' in os_info:
            #if val == "TASK1276383":
            logging.info("Processing Red Hat ticket %s", val)
            output = redhat_os_config(host)
            logging.info("Red Hat config result for %s: %s", val, output)
            success = "success" in output.lower() or "completed" in output.lower()
            for line in output.split("\n"):
                if "skipped" in line.lower() or "failed" in line.lower():
                    success = False
           
        elif 'Ubuntu' in os_info:
            #if val == "TASK1275730":
            logging.info("Processing Ubuntu ticket %s", val)
            output = ubuntu_os_config(host)
            logging.info("Ubuntu config result for %s: %s", val, output)
            success = "success" in output.lower() or "completed" in output.lower()
            for line in output.split("\n"):
                if "skipped" in line.lower() or "failed" in line.lower():
                    success = False
 
        else:
            logging.info("Ticket %s does not match Ubuntu/Red Hat -> assign to Linux Team", val)
            task_update(val, "OS not recognized - assign to Linux Team", stat_wip, assign_to, 'Linux Team', "OS not recognized")
            continue
       
        send_email(f"Automation Result {val}", output)
       
        if success:
            logging.info("Configuration successful for %s — closing ticket", val)
            task_close(val, output, stat_closed, assign_to, output, output, "Provisioning completed successfully")
        else:
            logging.info("Configuration NOT successful for %s — updating ticket", val)
            task_update(val, output, stat_wip, assign_to, output)
    logging.info("End of ticket cycle")    
   
if __name__ == '__main__':
    logging.info("Starting provisioning worker")
    try:
        while True:
            try:
                process_tickets_cycle()
            except Exception:
                logging.exception("Unhandled exception in processing cycle")
            SLEEP_DURATION = 300
            logging.info("Sleeping for %s seconds", SLEEP_DURATION)
            sleep(SLEEP_DURATION)
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
    except Exception:
        logging.exception("Stopped due to unexpected error")
    finally:
        logging.info("Worker stopped")
