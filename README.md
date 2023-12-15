# proxmox-ntfy
Monitor VM/LXC resource usage and send notifications to NTFY if usage thresholds are exceeded. 

To avoid notification spam, we keep a **vm_state.yml** file to save the gathered state, giving us something to compare against the next time the script run. We only want to send notifications when a resource state changes, say if Disk usage goes up from 55% (HEALTHY state) to 84% (WARNING state). If Disk usage moves from 82% to 85%, we don't need any notification.

Default thresholds:
- HEALTHY: 0%
- WARNING: 80%
- CRITICAL: 90%

We monitor CPU usage, RAM usage and Disk usage. Disk usage can't be tracked by default for VMs, so this monitor will technically only work for LXC's.

# Installation
All python dependencies should already be installed on Proxmox. We do need to install GIT to clone the repo.

### 1. Download the GIT repository to a folder:
Run the the following commands to clone the repository and enter the folder.
```
# apt install git
# cd && git clone https://github.com/emieli/proxmox-ntfy.git
# cd proxmox-ntfy/
```

### 2. Rename the config file
```
# mv config.yml.example config.yml
```

### 3. Run script once to verify that it works
```
root@proxmox:~/proxmox-ntfy# python3 main.py 
root@proxmox:~/proxmox-ntfy# 
```
*No output means everything went well.*

You should see a **vm_state.yml** file created in the folder, used as reference for "previous state" the next time the script runs, giving us some data to compare.

### 4. Create a root cronjob to run the script periodically
```
# crontab -e
no crontab for root - using an empty one

Select an editor.  To change later, run 'select-editor'.
  1. /bin/nano        <---- easiest
  2. /usr/bin/vim.tiny

Choose 1-2 [1]: 1
```

Add the following line to the bottom of the file:
```
# m   h  dom mon dow   command
*/15  *  *   *   *     cd /root/proxmox-ntfy && /usr/bin/python3 main.py
```

Press Ctrl+X followed by Y to save the changes. You can then use the **crontab -l** command to review, verifying that the changes were successfully added. You can also run the command in the shell to verify that the script ran without error.

The script should now run every 15 minutes and send notifications whenever a VM resource usage crosses different thresholds.

#### Example notification on ntfy.sh:
![](https://github.com/emieli/proxmox-ntfy/blob/main/example.png)

# Security
We are running the script as root. The reason for this is that only root is allowed to access the **pvesh** utility, and I couldn't be arsed to use the real REST API for communication locally on the server. Running everything as root is definitely not optimal.
