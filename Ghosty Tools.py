import os
import subprocess
import webbrowser
import threading
import sys
import ctypes
from PIL import Image
import customtkinter as ctk
from tkinter import messagebox
import pygame
import random
import time
import winreg
import psutil # type: ignore
import speedtest # type: ignore




# Initialize Pygame mixer
pygame.mixer.init()


current_dir = os.path.dirname(__file__)

# Define current directory for relative paths
def play_background_music():
    music_path = os.path.join(current_dir, "stream music.mp3")
    pygame.mixer.music.load(music_path)
    pygame.mixer.music.play(-1)
    pygame.mixer.music.set_volume(0.1)

def stop_background_music():
    pygame.mixer.music.stop()

# Start playing music by default
music_playing = True
play_background_music()

# Function to toggle music
def toggle_music():
    global music_playing
    if music_playing:
        stop_background_music()
    else:
        play_background_music()
    music_playing = not music_playing

play_background_music()

# button click sound
click_sound_path = os.path.join(current_dir, "button_click.mp3")
click_sound = pygame.mixer.Sound(click_sound_path)

def play_click_sound():
    click_sound.play()

# Check for admin privileges
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def elevate_privileges():
    script = os.path.abspath(sys.argv[0])
    params = ' '.join([script] + sys.argv[1:])
    try:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    except:
        print("Failed to elevate privileges.")
    sys.exit()

if not is_admin():
    elevate_privileges()

# Configure system settings
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Initialize App
app = ctk.CTk()
app.title("Ghosty Tool")
app.geometry("1330x520")
app.grid_rowconfigure(0, weight=1)
app.grid_columnconfigure(0, weight=1)
app.resizable(True, True)


def run_speed_test():
    speed_test_label.configure(text="Testing speed...")  # Update label during test
    speed_test = speedtest.Speedtest()

    # Run the speed test in a separate thread
    threading.Thread(target=perform_test, args=(speed_test,)).start()

def perform_test(speed_test):
    download_speed = speed_test.download() / 1_000_000  # Convert to Mbps
    upload_speed = speed_test.upload() / 1_000_000  # Convert to Mbps
    ping = speed_test.results.ping

    # Update the label with results
    result_text = f"Download Speed: {download_speed:.2f} Mbps\nUpload Speed: {upload_speed:.2f} Mbps\nPing: {ping:.2f} ms"
    speed_test_label.configure(text=result_text)

# Create the speed test button
speed_test_button = ctk.CTkButton(app, text="Run Speed Test",
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2, command=run_speed_test)
speed_test_button.grid(row=3, column=1, padx=20, pady=10)

# Create a label to display the speed test results
speed_test_label = ctk.CTkLabel(app, text="Click the button to test your speed.")
speed_test_label.grid(row=2, column=1, padx=20, pady=10)


def flush_dns():
    try:
        command = 'ipconfig /flushdns'
        subprocess.run(command, shell=True, check=True)
        messagebox.showinfo("Success", "DNS cache flushed successfully.")
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"Failed to flush DNS: {e}")

# Create a new frame for DNS Flush
dns_flush_frame = ctk.CTkFrame(app, width=300, height=150, fg_color="gray20")
dns_flush_frame.grid(row=0, column=3, padx=20, pady=20, sticky="n")

# Add a button to flush the DNS
flush_dns_button = ctk.CTkButton(dns_flush_frame, text="Flush DNS Cache", command=flush_dns)
flush_dns_button.pack(pady=30)

# Optional: You can add a label to provide some information
dns_info_label = ctk.CTkLabel(dns_flush_frame, text="Click to flush DNS cache", font=("Helvetica", 12), text_color="white")
dns_info_label.pack(pady=5)

# Function to check disk health using WMIC (Windows Management Instrumentation Command)
def check_disk_health():
    try:
        # Run WMIC command to check disk health via SMART
        command = 'wmic diskdrive get status'
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        # Process the result
        if "OK" in result.stdout:
            disk_status_label.configure(text="Disk Health: Healthy", text_color="green")
        else:
            disk_status_label.configure(text="Disk Health: Issues Detected", text_color="red")
            tips_disk_label.configure(text="Tip: Consider backing up your data and replacing the drive.")

    except Exception as e:
        print(f"Error checking disk health: {e}")
        disk_status_label.configure(text="Error: Unable to check disk health")
        tips_disk_label.configure(text="")

    # Schedule the next check after 60 seconds (60000 milliseconds)
    app.after(60000, check_disk_health)  # 60 seconds

# Create a new frame for Disk Health Check
disk_health_frame = ctk.CTkFrame(app, width=300, height=150, fg_color="gray20")
disk_health_frame.grid(row=0, column=2, padx=20, pady=20, sticky="n")

# Label to display disk health status
disk_status_label = ctk.CTkLabel(disk_health_frame, text="Disk Health: Checking...", font=("Helvetica", 16), text_color="white")
disk_status_label.pack(pady=5)

# Label to display disk tips
tips_disk_label = ctk.CTkLabel(disk_health_frame, text="Disk Tip: --", font=("Helvetica", 12), text_color="white")
tips_disk_label.pack(pady=5)

# Add a button to manually check disk health
disk_check_button = ctk.CTkButton(disk_health_frame, text="Check Disk Health", command=check_disk_health)
disk_check_button.pack(pady=10)

# Check disk health when the app starts and continue checking every 60 seconds
check_disk_health()


def update_battery_health():
    while True:
        battery = psutil.sensors_battery()  # Get battery information
        if battery is not None:
            battery_percentage = battery.percent  # Battery percentage
            power_plugged = battery.power_plugged  # True if plugged in, False otherwise
            time_left = battery.secsleft if not power_plugged else "Charging"
            
            if isinstance(time_left, int):
                hours, remainder = divmod(time_left, 3600)
                minutes = remainder // 60
                time_left = f"{hours}h {minutes}m remaining"
            else:
                time_left = "Charging" if power_plugged else "N/A"
            
            # Update battery label
            battery_label.configure(text=f"Battery: {battery_percentage}% - {time_left}")
            
            # Update tips based on battery status
            if power_plugged:
                tips_label.configure(text="Battery Tip: Avoid keeping your laptop plugged in all the time.")
            else:
                tips_label.configure(text="Battery Tip: Dim your screen and close unused programs to save battery.")
        
        else:
            battery_label.configure(text="Battery: No battery detected")
            tips_label.configure(text="Battery Tip: Laptops without a battery should be used with care.")

        time.sleep(60)  # Update every 60 seconds

# Create a new frame for the Battery Health Monitor
battery_frame = ctk.CTkFrame(app, width=300, height=150, fg_color="gray20")
battery_frame.grid(row=0, column=4, padx=20, pady=20, sticky="n")

# Create a label for Battery Health
battery_label = ctk.CTkLabel(battery_frame, text="Battery: --%", font=("Helvetica", 16), text_color="white")
battery_label.pack(pady=5)

# Create a label for Battery Tips
tips_label = ctk.CTkLabel(battery_frame, text="Battery Tip: --", font=("Helvetica", 12), text_color="white")
tips_label.pack(pady=5)

# Start the battery health monitoring in a separate thread
threading.Thread(target=update_battery_health, daemon=True).start()


def update_system_usage():
    while True:
        cpu_usage = psutil.cpu_percent(interval=1)  # Get CPU usage in percentage
        ram_usage = psutil.virtual_memory().percent  # Get RAM usage in percentage
        
        # Update labels with current CPU and RAM usage
        cpu_label.configure(text=f"CPU Usage: {cpu_usage}%")
        ram_label.configure(text=f"RAM Usage: {ram_usage}%")
        
        time.sleep(1)  # Update every second

# Create a new frame for the CPU/RAM Usage Monitor
monitor_frame = ctk.CTkFrame(app, width=300, height=100, fg_color="gray20")
monitor_frame.grid(row=0, column=1, padx=20, pady=20, sticky="n")

# Create labels for CPU and RAM usage
cpu_label = ctk.CTkLabel(monitor_frame, text="CPU Usage: --%", font=("Helvetica", 16), text_color="white")
cpu_label.pack(pady=5)

ram_label = ctk.CTkLabel(monitor_frame, text="RAM Usage: --%", font=("Helvetica", 16), text_color="white")
ram_label.pack(pady=5)

# Start the system usage update in a separate thread to prevent blocking the main app
threading.Thread(target=update_system_usage, daemon=True).start()



def create_tweaks_subheader():
    tweaks_label = ctk.CTkLabel(app, text="Mini Games", font=("Helvetica", 20, "bold"), text_color="#993cda")
    tweaks_label.grid(row=3, column=2, padx=37, pady=(15, 0), sticky="nw")


create_tweaks_subheader()

# Load images
def load_image(image_name, size):
    image_path = os.path.join(current_dir, "images", image_name)
    if not os.path.isfile(image_path):
        print(f"Error: Image {image_name} not found at {image_path}.")
        return None
    return ctk.CTkImage(Image.open(image_path), size=size)

# label with image
def create_label_with_image(text, image_name, row, column, text_color="#993cda"):
    loaded_image = load_image(image_name, size=(85, 85))
    if loaded_image:
        label = ctk.CTkLabel(app, text=text, font=("Helvetica", 25, "bold"),
                             image=loaded_image, text_color=text_color, compound="left")
        label.grid(row=row, column=column, pady=(30, 0), sticky="nsew")

# Function to check for Windows updates
def check_for_windows_updates():
    if messagebox.askyesno("Check for Windows Updates", "Would you like to check for available updates?"):
        threading.Thread(target=run_windows_update_check).start()

# Function to run the Windows update check
def run_windows_update_check():
    try:
        print("Checking for Windows updates...")
        # Running Windows Update command to check for available updates
        result = subprocess.run(
            "powershell -Command \"Get-WindowsUpdate\"",
            shell=True, capture_output=True, text=True
        )
        print("PowerShell output:\n", result.stdout)  # Print the full output for debugging

        # Check if there are any updates in the output
        if "No updates available" in result.stdout:  # Adjust this string based on actual output
            messagebox.showinfo("Updates", "Your system is up to date.")
        elif "Updates are available" in result.stdout:  # Check for another possible output string
            messagebox.showinfo("Updates", "Updates are available! Proceed to install?")
            # Option to install updates
            if messagebox.askyesno("Install Updates", "Do you want to install the updates now?"):
                install_windows_updates()
        else:
            messagebox.showinfo("Updates", "Check completed, but no specific information available.")
            
    except Exception as e:
        print(f"Error checking for updates: {e}")
        messagebox.showerror("Error", f"Error checking for updates: {e}")


# Function to install Windows updates
def install_windows_updates():
    try:
        print("Installing updates...")
        # Command to install available updates
        subprocess.run(
            "powershell -Command \"Install-WindowsUpdate -AcceptAll -AutoReboot\"",
            shell=True
        )
        messagebox.showinfo("Updates", "Updates installed successfully! Your system may reboot.")
    except Exception as e:
        print(f"Error installing updates: {e}")
        messagebox.showerror("Error", f"Error installing updates: {e}")

# Function to open a webpage
def open_webpage(url):
    try:
        webbrowser.open_new_tab(url)
    except webbrowser.Error:
        print(f"Failed to open {url} link.")

# Create footer labels
def create_footer_label(image_name, command, row, column):
    footer_image = load_image(image_name, size=(25, 25))  # Assuming load_image is defined elsewhere
    footer_label = ctk.CTkLabel(app, text="", image=footer_image, text_color="#993cda", compound="center")
    footer_label.grid(row=row, column=column, pady=10)
    footer_label.bind("<Button-1>", lambda e: command())

create_footer_label("GithubLogo.png", lambda: open_webpage("https://github.com/Ghostshadowplays"), 8, 0)
create_footer_label("twitchlogo.png", lambda: open_webpage("https://twitch.tv/ghostshadow_plays"), 8, 1)

# Global variable to hold the main disk
main_disk = None

def get_main_disk():
    global main_disk  # Use the global variable
    try:
        powershell_script = '''
        $MainDisk = 0
        ForEach ($disk in (Get-PhysicalDisk | Select-Object DeviceID, MediaType, Size)){
            If ($disk.MediaType -eq 'SSD' -and $disk.Size -gt 100GB){
                $MainDisk = $disk.DeviceID
                break
            }
        }
        $MainDisk
        '''
        
        result = subprocess.run(
            ["powershell", "-Command", powershell_script],
            capture_output=True,
            text=True,
            shell=True
        )
        main_disk = result.stdout.strip()
        if main_disk:
            print(f"Main disk detected: {main_disk}")
        else:
            print("No suitable disk found.")
    except Exception as e:
        print(f"Error getting main disk: {e}")


# Global variable for "Select All" checkbox
select_all_var = ctk.BooleanVar()

# Checkbox for "Select All"
select_all_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Select All Tweaks",
    fg_color="#4158D0",
    text_color="#FFFFFF",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=select_all_var,
    command=lambda: toggle_all_checkboxes(select_all_var.get())
)
select_all_checkbox.grid(row=8, column=2, padx=20, pady=10, sticky="w")

def toggle_all_checkboxes(select_all):
    # Update all other checkbox variables based on the state of the "Select All" checkbox
    delete_temp_files_var.set(select_all)
    disable_telemetry_var.set(select_all)
    disable_activity_history_var.set(select_all)
    disable_gamedvr_var.set(select_all)
    create_restore_point_var.set(select_all)
    disable_hibernation_var.set(select_all)
    disable_homegroup_var.set(select_all)
    prefer_ipv4_var.set(select_all)
    disable_location_tracking_var.set(select_all)
    disable_storage_sense_var.set(select_all)
    disable_wifi_sense_var.set(select_all)
    enable_end_task_var.set(select_all)
    run_disk_cleanup_var.set(select_all)
    set_services_manual_var.set(select_all)
    check_updates_var.set(select_all)  


check_updates_var = ctk.IntVar()  

check_updates_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Check for Windows Updates",
    fg_color="#4158D0",
    text_color="#FFFFFF",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=check_updates_var  
)
check_updates_checkbox.grid(row=5, column=4, padx=20, pady=10, sticky="w")


def execute_maintenance_tasks():
    global main_disk  
    try:
        print("Creating restore point...")
        create_restore_point()

        if main_disk:
            print(f"Performing maintenance on main disk: {main_disk}")
            defrag_command = f"defrag {main_disk} /u"  # Prepare defrag command

        # Continue with other maintenance commands
        commands = (
            "DISM.exe /Online /Cleanup-Image /CheckHealth; "
            "DISM.exe /Online /Cleanup-Image /ScanHealth; "
            "DISM.exe /Online /Cleanup-Image /RestoreHealth; "
            "sfc /scannow; "
            "gpupdate /force; "
            "chkdsk /f /r; "
        )
        subprocess.run(
            f'powershell -Command "Start-Process PowerShell -ArgumentList \'-NoProfile\', \'-Command {commands}\' -Verb RunAs"',
            shell=True
        )

        # Check for Windows updates based on the checkbox
        if check_updates_var.get() == 1:  
            run_windows_update_check()  

        # Ask to run defragmentation after other maintenance tasks
        if main_disk and messagebox.askyesno("Run Defragmentation", f"Do you want to defragment {main_disk}?"):
            subprocess.run(f'powershell -Command "{defrag_command}"', shell=True)

        print("Maintenance tasks completed.")
    except Exception as e:
        print(f"Error executing maintenance tasks: {e}")
        messagebox.showerror("Error", f"Error executing maintenance tasks: {e}")

def run_windows_update_check():
    try:
        print("Checking for Windows updates...")
        # Running Windows Update command to check for available updates
        result = subprocess.run(
            "powershell -Command \"Get-WindowsUpdate\"",
            shell=True, capture_output=True, text=True
        )
        print(result.stdout)
        
        if "No updates" in result.stdout:  
            messagebox.showinfo("Updates", "Your system is up to date.")
        else:
            messagebox.showinfo("Updates", "Updates are available! Proceed to install?")
            if messagebox.askyesno("Install Updates", "Do you want to install the updates now?"):
                install_windows_updates()

    except Exception as e:
        print(f"Error checking for updates: {e}")
        messagebox.showerror("Error", f"Error checking for updates: {e}")

def install_windows_updates():
    try:
        print("Installing updates...")
        subprocess.run(
            "powershell -Command \"Install-WindowsUpdate -AcceptAll -AutoReboot\"",
            shell=True
        )
        messagebox.showinfo("Updates", "Updates installed successfully! Your system may reboot.")
    except Exception as e:
        print(f"Error installing updates: {e}")
        messagebox.showerror("Error", f"Error installing updates: {e}")


def run_system_maintenance():
    get_main_disk()  # Get the main disk before starting maintenance
    if messagebox.askyesno("Run Full System Maintenance", "This may take a while. Proceed?"):
        threading.Thread(target=execute_maintenance_tasks).start()



# MBR2GPT Conversion
def run_mbr2gpt_command():
    selected_command = mbr2gpt_combo.get()
    if messagebox.askyesno("MBR to GPT Conversion", f"Proceed with: {selected_command}?"):
        try:
            subprocess.run(selected_command, shell=True, check=True)
            messagebox.showinfo("Success", "Command executed successfully.")
        except Exception as e:
            print(f"Error executing {selected_command}: {e}")
            messagebox.showerror("Error", f"Error executing {selected_command}: {e}")

mbr2gpt_options = [
    "mbr2gpt /validate /disk:0 /allowFullOS",
    "mbr2gpt /validate /disk:1 /allowFullOS",
    "mbr2gpt /validate /disk:2 /allowFullOS",
    "mbr2gpt /validate /disk:3 /allowFullOS",
    "mbr2gpt /convert /disk:0 /allowFullOS",
    "mbr2gpt /convert /disk:1 /allowFullOS",
    "mbr2gpt /convert /disk:2 /allowFullOS",
    "mbr2gpt /convert /disk:3 /allowFullOS"
]

# Button for MBR2GPT options
mbr2gpt_combo = ctk.CTkComboBox(app, values=mbr2gpt_options, width=300, height=30)
mbr2gpt_combo.set("Select MBR2GPT Command")
mbr2gpt_combo.grid(row=2, column=0, padx=20, pady=15, sticky="w")

run_button = ctk.CTkButton(
    master=app,
    text="Run MBR2GPT",
    command=lambda: [play_click_sound(), run_mbr2gpt_command()],
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2
)
run_button.grid(row=3, column=0, padx=47, pady=15, sticky="w")

create_label_with_image("Ghosty Tools", "image_1.png", 0, 0)

# Button with Image
def create_button_with_image(image_name, text, command, row, column):
    loaded_image = load_image(image_name, size=(20, 20))
    if loaded_image:
        button = ctk.CTkButton(
            master=app,
            image=loaded_image,
            text=text,
            corner_radius=32,
            fg_color="#4158D0",
            hover_color="#993cda",
            border_color="#e7e7e7",
            border_width=2,
            command=lambda: [play_click_sound(), command()]
        )
        button.grid(row=row, column=column, padx=20, pady=15, sticky="w")

def create_button(text, command, row, column):
    button = ctk.CTkButton(
        master=app,
        text=text,
        corner_radius=32,
        fg_color="#4158D0",
        hover_color="#993cda",
        border_color="#e7e7e7",
        border_width=2,
        command=lambda: [play_click_sound(), command()]  
    )
    button.grid(row=row, column=column, padx=20, pady=15, sticky="w")

# Click the Target
def play_mini_game():
    
    pygame.display.set_mode((400, 300))
    pygame.display.set_caption("Click the Target")
    
    # Define target properties
    target_color = (255, 0, 0)  
    target_radius = 20
    target_pos = (random.randint(target_radius, 380), random.randint(target_radius, 280))

    # game variables
    score = 0
    game_duration = 15  
    start_time = time.time()

# Click the Target
def play_mini_game():
   
    pygame.font.init()
    
    
    pygame.display.set_mode((400, 300))
    pygame.display.set_caption("Click the Target")
    
    
    target_color = "#993cda" 
    target_radius = 20
    target_pos = (random.randint(target_radius, 380), random.randint(target_radius, 280))

    # game variables
    score = 0
    game_duration = 15 
    start_time = time.time()

  
    running = True
    while running:
        pygame.display.get_surface().fill((30, 30, 30))  # White background
        pygame.draw.circle(pygame.display.get_surface(), target_color, target_pos, target_radius)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()
                
                distance = ((mouse_pos[0] - target_pos[0]) ** 2 + (mouse_pos[1] - target_pos[1]) ** 2) ** 0.5
                if distance <= target_radius:
                    click_sound.play()  
                    score += 1
                    
                    target_pos = (random.randint(target_radius, 380), random.randint(target_radius, 280))

        # Check if game time is over
        if time.time() - start_time > game_duration:
            running = False

        # Display the score
        font = pygame.font.Font(None, 36)
        score_text = font.render(f"Score: {score}", True, (255, 255, 255))
        pygame.display.get_surface().blit(score_text, (10, 10))

        pygame.display.flip()

    # Return to main app window after game
    pygame.display.quit()
    pygame.font.quit()
    messagebox.showinfo("Click the Target Over", f"Your score: {score}")

# Tic-Tac-Toe

def play_tic_tac_toe():
    pygame.init()
    screen = pygame.display.set_mode((400, 400))
    pygame.display.set_caption("Tic-Tac-Toe")

    WHITE = (255, 255, 255)
    RED = (255, 0, 0)
    BLUE = (0, 0, 255)

    grid = [['' for _ in range(3)] for _ in range(3)]
    current_player = 'X'
    game_over = False

    def draw_grid():
        for i in range(1, 3):
            pygame.draw.line(screen, WHITE, (0, i * 133), (400, i * 133), 2)
            pygame.draw.line(screen, WHITE, (i * 133, 0), (i * 133, 400), 2)

    def draw_marks():
        for row in range(3):
            for col in range(3):
                mark = grid[row][col]
                if mark == 'X':
                    pygame.draw.line(screen, RED, (col * 133 + 20, row * 133 + 20), (col * 133 + 113, row * 133 + 113), 2)
                    pygame.draw.line(screen, RED, (col * 133 + 20, row * 133 + 113), (col * 133 + 113, row * 133 + 20), 2)
                elif mark == 'O':
                    pygame.draw.circle(screen, BLUE, (col * 133 + 67, row * 133 + 67), 50, 2)

    def check_winner():
        for row in range(3):
            if grid[row][0] == grid[row][1] == grid[row][2] != '':
                return grid[row][0]
        for col in range(3):
            if grid[0][col] == grid[1][col] == grid[2][col] != '':
                return grid[0][col]
        if grid[0][0] == grid[1][1] == grid[2][2] != '':
            return grid[0][0]
        if grid[0][2] == grid[1][1] == grid[2][0] != '':
            return grid[0][2]
        return None

    def check_draw():
        return all(cell != '' for row in grid for cell in row)

    running = True
    while running:
        screen.fill((30, 30, 30))
        draw_grid()
        draw_marks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and not game_over:
                mouseX, mouseY = event.pos
                col = mouseX // 133
                row = mouseY // 133

                if grid[row][col] == '':
                    grid[row][col] = current_player
                    winner = check_winner()

                    if winner:
                        messagebox.showinfo("Game Over", f"{winner} wins!")
                        game_over = True
                    elif check_draw():
                        messagebox.showinfo("Game Over", "It's a draw!")
                        game_over = True
                    else:
                        current_player = 'O' if current_player == 'X' else 'X'

            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                grid = [['' for _ in range(3)] for _ in range(3)]
                current_player = 'X'
                game_over = False

        pygame.display.flip()

    pygame.display.quit()  


def start_game():
    game_thread = threading.Thread(target=play_tic_tac_toe)
    game_thread.start()


    


# variable for the checkbox to set services to manual
set_services_manual_var = ctk.BooleanVar()

#  checkbox for setting services to manual
set_services_manual_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Set Services to Manual",
    text_color="#FFFFFF",
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=set_services_manual_var
)
set_services_manual_checkbox.grid(row=2, column=3, padx=20, pady=10, sticky="w")

def set_services_to_manual(service_names):
    for service in service_names:
        try:
            command = f'Sc config "{service}" start= demand'
            subprocess.run(command, shell=True, check=True, capture_output=True)
            print(f"Service '{service}' set to manual.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to set service '{service}' to manual: {e.stderr}")
            if service == "Dnscache":
                print(f"Service '{service}' requires special permissions and cannot be modified.")
            else:
                messagebox.showerror("Error", f"Failed to set service '{service}' to manual: {e.stderr}")


services_to_set_manual = [
    "wuauserv",
    "BITS",
    
]


run_disk_cleanup_var = ctk.BooleanVar()

# checkbox for running Disk Cleanup
run_disk_cleanup_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Run Disk Cleanup",
    fg_color="#4158D0",
    text_color="#FFFFFF",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=run_disk_cleanup_var
)
run_disk_cleanup_checkbox.grid(row=5, column=3, padx=20, pady=10, sticky="w")

def run_disk_cleanup():
    # Call the Disk Cleanup utility
    try:
        subprocess.run("cleanmgr.exe", shell=True)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to run Disk Cleanup: {e}")

# variable for the checkbox to enable End Task with Right Click
enable_end_task_var = ctk.BooleanVar()

# checkbox for enabling End Task with Right Click
enable_end_task_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Enable End Task With Right Click",
    fg_color="#4158D0",
    text_color="#FFFFFF",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=enable_end_task_var
)
enable_end_task_checkbox.grid(row=5, column=2, padx=20, pady=10, sticky="w")

def enable_end_task():
   
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "NoViewContextMenu", 0, winreg.REG_DWORD, 0)  
        winreg.CloseKey(key)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to enable End Task with Right Click: {e}")



disable_wifi_sense_var = ctk.BooleanVar()


disable_wifi_sense_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Disable Wi-Fi Sense",
    fg_color="#4158D0",
    text_color="#FFFFFF",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=disable_wifi_sense_var
)
disable_wifi_sense_checkbox.grid(row=4, column=4, padx=20, pady=10, sticky="w")

def disable_wifi_sense():
    try:
        
        key_path = r"SOFTWARE\Microsoft\WcmSvc\wifinetworkmanager\config"
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE)
        except FileNotFoundError:
            
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path)

        winreg.SetValueEx(key, "AutoConnectAllowedOEM", 0, winreg.REG_DWORD, 0)  # Set to 0 to disable
        winreg.CloseKey(key)
        print("Wi-Fi Sense disabled.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to disable Wi-Fi Sense: {e}")


disable_storage_sense_var = ctk.BooleanVar()


disable_storage_sense_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Disable Storage Sense",
    fg_color="#4158D0",
    text_color="#FFFFFF",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=disable_storage_sense_var
)
disable_storage_sense_checkbox.grid(row=3, column=4, padx=20, pady=10, sticky="w")

def disable_storage_sense():
    try:
        
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy"
        
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE)
        except FileNotFoundError:
            
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path)

        winreg.SetValueEx(key, "01", 0, winreg.REG_DWORD, 0) 
        winreg.CloseKey(key)
        print("Storage Sense disabled.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to disable Storage Sense: {e}")


disable_location_tracking_var = ctk.BooleanVar()


disable_location_tracking_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Disable Location Tracking",
    fg_color="#4158D0",
    text_color="#FFFFFF",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=disable_location_tracking_var
)
disable_location_tracking_checkbox.grid(row=2, column=4, padx=20, pady=10, sticky="w")

def disable_location_tracking():
    
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "Value", 0, winreg.REG_DWORD, 0)  
        winreg.CloseKey(key)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to disable location tracking: {e}")

# variable for the checkbox to prefer IPv4 over IPv6
prefer_ipv4_var = ctk.BooleanVar()

# checkbox for preferring IPv4 over IPv6
prefer_ipv4_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Prefer IPv4 over IPv6",
    fg_color="#4158D0",
    text_color="#FFFFFF",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=prefer_ipv4_var
)
prefer_ipv4_checkbox.grid(row=1, column=4, padx=20, pady=10, sticky="w")

def prefer_ipv4():
    try:
        # Path to the TCPIP parameters
        key_path = r"SOFTWARE\Policies\Microsoft\Windows\TCPIP"
        
        # Try to open the TCPIP key
        try:
            tcpip_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE)
        except FileNotFoundError:
            
            tcpip_key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path)
        
        # Now create the Parameters key
        parameters_key = winreg.CreateKey(tcpip_key, "Parameters")
        
        # Set the value to prefer IPv4
        winreg.SetValueEx(parameters_key, "IPEnableRouter", 0, winreg.REG_DWORD, 1)  # Set to 1 to prefer IPv4
        
        # Clean up
        winreg.CloseKey(parameters_key)
        winreg.CloseKey(tcpip_key)
        
        print("IP preference configured to prefer IPv4.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to configure IP preference: {e}")

disable_homegroup_var = ctk.BooleanVar()


disable_homegroup_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Disable HomeGroup",
    fg_color="#4158D0",
    text_color="#FFFFFF",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=disable_homegroup_var
)
disable_homegroup_checkbox.grid(row=4, column=3, padx=20, pady=10, sticky="w")

def disable_homegroup():
    
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "HomeGroupDisabled", 1, winreg.REG_DWORD, 1)  # Set to 1 to disable HomeGroup
        winreg.CloseKey(key)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to disable HomeGroup: {e}")

def run_defrag():
    try:
        subprocess.run(["defrag", "C:", "/u"], check=True)
        print("Defragmentation started.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to run defrag: {e}")


delete_temp_files_var = ctk.BooleanVar()


delete_temp_files_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Delete Temporary Files",
    fg_color="#4158D0",
    text_color="#FFFFFF",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=delete_temp_files_var
)
delete_temp_files_checkbox.grid(row=2, column=2, padx=20, pady=10, sticky="w")

def delete_temp_files():
    
    temp_folder = os.path.join(os.getenv('TEMP'))

    
    if not os.path.exists(temp_folder):
        messagebox.showerror("Error", "Temporary files folder not found.")
        return

    try:
        
        for filename in os.listdir(temp_folder):
            file_path = os.path.join(temp_folder, filename)
            
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)  
                    print(f"Deleted: {file_path}")  
                except PermissionError:
                    print(f"Permission denied: {file_path} is in use or locked.")
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")  

    except Exception as e:
        print(f"Error deleting temporary files: {e}")  
        messagebox.showerror("Error", f"Error deleting temporary files: {e}")


disable_hibernation_var = ctk.BooleanVar()


disable_hibernation_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Disable Hibernation",
    fg_color="#4158D0",
    text_color="#FFFFFF",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=disable_hibernation_var
)
disable_hibernation_checkbox.grid(row=3, column=3, padx=20, pady=10, sticky="w")




def disable_hibernation():
    
    try:
        subprocess.run('powercfg -h off', shell=True, check=True)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to disable hibernation: {e}")


disable_telemetry_var = ctk.BooleanVar()


disable_telemetry_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Disable Telemetry",
    fg_color="#4158D0",
    text_color="#FFFFFF",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=disable_telemetry_var
)
disable_telemetry_checkbox.grid(row=3, column=2, padx=20, pady=10, sticky="w")

def disable_telemetry():
    
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "AllowTelemetry", 0, winreg.REG_DWORD, 0)  # Set to 0 to disable telemetry
        winreg.CloseKey(key)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to disable telemetry: {e}")


disable_activity_history_var = ctk.BooleanVar()


disable_activity_history_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Disable Activity History",
    fg_color="#4158D0",
    text_color="#FFFFFF",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=disable_activity_history_var
)
disable_activity_history_checkbox.grid(row=4, column=2, padx=20, pady=10, sticky="w")

def disable_activity_history():
    
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Privacy", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "ActivityHistoryEnabled", 0, winreg.REG_DWORD, 0)  # Set to 0 to disable activity history
        winreg.CloseKey(key)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to disable activity history: {e}")


disable_gamedvr_var = ctk.BooleanVar()


disable_gamedvr_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Disable GameDVR",
    text_color="#FFFFFF",
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=disable_gamedvr_var
)
disable_gamedvr_checkbox.grid(row=1, column=3, padx=20, pady=10, sticky="w")

def disable_gamedvr():
    
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\GameDVR", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "AppCaptureEnabled", 0, winreg.REG_DWORD, 0)  # Set to 0 to disable GameDVR
        winreg.CloseKey(key)

        
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\GameDVR", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "GameDVR_Enabled", 0, winreg.REG_DWORD, 0)  # Set to 0 to disable Game Bar
        winreg.CloseKey(key)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to disable GameDVR: {e}")

create_restore_point_var = ctk.BooleanVar()


create_restore_point_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Create Restore Point",
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    text_color="#FFFFFF",
    border_width=2,
    variable=create_restore_point_var
)
create_restore_point_checkbox.grid(row=1, column=2, padx=20, pady=10, sticky="w")

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


# Function to enable system protection for C: drive
def enable_system_protection():
    try:
        # Run the PowerShell command to enable system restore protection on C: drive
        command = ['powershell', '-Command', 'Enable-ComputerRestore -Drive "C:\\"']
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode == 0:
            return True  # Indicate success
        else:
            messagebox.showerror("Error", f"Failed to enable system protection: {result.stderr}")
            return False  # Indicate failure
    except Exception as e:
        messagebox.showerror("Error", f"Error enabling system protection: {e}")
        return False

# Function to create a restore point
def create_restore_point():
    if messagebox.askyesno("Create Restore Point", "Proceed to create a restore point?"):
        try:
            # Enable system protection on C: drive before creating the restore point
            if enable_system_protection():
                # Proceed to create the restore point if protection was successfully enabled
                command = "Checkpoint-Computer -Description 'Restore Point created by Ghosty Tool' -RestorePointType 'APPLICATION_INSTALL'"
                subprocess.run(f'powershell -Command "{command}"', shell=True, check=True)
                messagebox.showinfo("Success", "Restore point created successfully.")
            else:
                messagebox.showerror("Error", "Failed to enable system protection. Restore point creation aborted.")
        except Exception as e:
            print(f"Error creating restore point: {e}")
            messagebox.showerror("Error", f"Error creating restore point: {e}")


confirm_button = ctk.CTkButton(
    master=app,
    corner_radius=32,
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    text="Confirm Changes",
    command=lambda: [play_click_sound(),confirm_changes()]

)
confirm_button.grid(row=8, column=4, padx=20, pady=10, sticky="w")

def toggle_dark_mode():
    
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", 0, winreg.KEY_READ)
        current_value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)

        # Toggle the value
        new_value = 0 if current_value == 1 else 1  

        
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, new_value)
        winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, new_value)
        winreg.CloseKey(key)

        
    except Exception as e:
        messagebox.showerror("Error", f"Failed to toggle Dark Mode: {e}")

def toggle_background_color():
    current_bg_color = app.cget("fg_color") 
    

    if current_bg_color == "#1c1c1c": 
        app.configure(fg_color="#f0f0f0")  
    else:
        app.configure(fg_color="#1c1c1c")  


# Default background color (dark)
app.configure(fg_color="#1c1c1c")


def confirm_changes():

    if create_restore_point_var.get():
        create_restore_point()


    # Handle deleting temporary files
    if delete_temp_files_var.get():
        delete_temp_files()

    # Handle disabling telemetry
    if disable_telemetry_var.get():
        disable_telemetry()

    # Handle disabling activity history
    if disable_activity_history_var.get():
        disable_activity_history()

    # Handle disabling GameDVR
    if disable_gamedvr_var.get():
        disable_gamedvr()

    if disable_hibernation_var.get():
        disable_hibernation()

      # Handle disabling HomeGroup
    if disable_homegroup_var.get():
        disable_homegroup()

      # Handle preferring IPv4 over IPv6
    if prefer_ipv4_var.get():
        prefer_ipv4()

        # Handle disabling location tracking
    if disable_location_tracking_var.get():
        disable_location_tracking()

      # Handle disabling Storage Sense
    if disable_storage_sense_var.get():
        disable_storage_sense()

       # Handle disabling Wi-Fi Sense
    if disable_wifi_sense_var.get():
        disable_wifi_sense()

      # Handle enabling End Task with Right Click
    if enable_end_task_var.get():
        enable_end_task()

     # Handle running Disk Cleanup
    if run_disk_cleanup_var.get():
        run_disk_cleanup()
    
       # Handle setting services to manual
    if set_services_manual_var.get():
        set_services_to_manual(services_to_set_manual)

    if check_updates_var.get():
        run_windows_update_check()


    messagebox.showinfo("Settings Applied", "Your changes have been applied.")

create_button_with_image("repairlogo.png", "Run System Maintenance", run_system_maintenance, 1, 0)
create_button("Play Click The Target", play_mini_game, 4, 1,)
start_button = ctk.CTkButton(app, text="Play Tic-Tac-Toe",
    corner_radius=32,
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2, command=start_game)
start_button.grid(pady=20, padx=20, row = 5, column = 1,)
music_switch = ctk.CTkSwitch(app, text="Music, On-Off", border_color="#e7e7e7", fg_color="#4158D0", border_width=2,  button_hover_color="#993cda", text_color="#FFFFFF", command=toggle_music)
music_switch.grid(row=4, column=0, padx=1, pady=15)
dark_mode_switch = ctk.CTkSwitch(app, text="Windows Dark Or Light Mode", border_color="#e7e7e7", fg_color="#4158D0", border_width=2,  button_hover_color="#993cda", text_color="#FFFFFF", command=toggle_dark_mode)
dark_mode_switch.grid(row=1, column=1, padx=20, pady=20)
bg_color_switch = ctk.CTkSwitch(app, text="Toggle Background Color", border_color="#e7e7e7", fg_color="#4158D0", border_width=2,  button_hover_color="#993cda", text_color="#FFFFFF", command=toggle_background_color)
bg_color_switch.grid(row=5, column=0, padx=20, pady=20)

app.mainloop()
