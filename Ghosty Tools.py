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

# Initialize Pygame mixer
pygame.mixer.init()

# Define current directory for relative paths
current_dir = os.path.dirname(__file__)

# Play background music
def play_background_music():
    music_path = os.path.join(current_dir, "stream music.mp3")
    pygame.mixer.music.load(music_path)
    pygame.mixer.music.play(-1)
    pygame.mixer.music.set_volume(0.1)

play_background_music()

# Load button click sound
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
app.geometry("1110x410")
app.grid_rowconfigure(0, weight=1)
app.grid_columnconfigure(0, weight=1)
app.resizable(True, True)

# Create a subheader label for "Tweaks"
def create_tweaks_subheader():
    tweaks_label = ctk.CTkLabel(app, text="Tweaks", font=("Helvetica", 20, "bold"), text_color="#993cda")
    tweaks_label.grid(row=0, column=2, padx=50, pady=(50, 0), sticky="nw")

# Call the function to create the subheader
create_tweaks_subheader()

def create_tweaks_subheader():
    tweaks_label = ctk.CTkLabel(app, text="Mini Games", font=("Helvetica", 20, "bold"), text_color="#993cda")
    tweaks_label.grid(row=3, column=1, padx=37, pady=(15, 0), sticky="nw")

# Call the function to create the subheader
create_tweaks_subheader()

# Load images
def load_image(image_name, size):
    image_path = os.path.join(current_dir, "images", image_name)
    if not os.path.isfile(image_path):
        print(f"Error: Image {image_name} not found at {image_path}.")
        return None
    return ctk.CTkImage(Image.open(image_path), size=size)

# Create label with image
def create_label_with_image(text, image_name, row, column, text_color="#993cda"):
    loaded_image = load_image(image_name, size=(40, 40))
    if loaded_image:
        label = ctk.CTkLabel(app, text=text, font=("Helvetica", 25, "bold"),
                             image=loaded_image, text_color=text_color, compound="left")
        label.grid(row=row, column=column, pady=(30, 0), sticky="nsew")

# Open webpage
def open_webpage(url):
    try:
        webbrowser.open_new_tab(url)
    except webbrowser.Error:
        print(f"Failed to open {url} link.")

# Create footer labels
def create_footer_label(image_name, command, row, column):
    footer_image = load_image(image_name, size=(25, 25))
    footer_label = ctk.CTkLabel(app, text="", image=footer_image, text_color="#993cda", compound="center")
    footer_label.grid(row=row, column=column, pady=10)
    footer_label.bind("<Button-1>", lambda e: command())

create_footer_label("GithubLogo.png", lambda: open_webpage("https://github.com/Ghostshadowplays"), 8, 0)
create_footer_label("twitchlogo.png", lambda: open_webpage("https://twitch.tv/ghostshadow_plays"), 8, 1)

# System Maintenance Functions
def run_system_maintenance():
    if messagebox.askyesno("Run Full System Maintenance", "This may take a while. Proceed?"):
        threading.Thread(target=execute_maintenance_tasks).start()

def execute_maintenance_tasks():
    try:
        print("Creating restore point...")
        create_restore_point()

        commands = (
            "DISM.exe /Online /Cleanup-Image /CheckHealth; "
            "DISM.exe /Online /Cleanup-Image /ScanHealth; "
            "DISM.exe /Online /Cleanup-Image /RestoreHealth; "
            "sfc /scannow; "
            "gpupdate /force; "
            "chkdsk /f /r; "
            "cleanmgr; "
            "defrag C: /u"
        )
        subprocess.run(
            f'powershell -Command "Start-Process PowerShell -ArgumentList \'-NoProfile\', \'-Command {commands}\' -Verb RunAs"',
            shell=True
        )
        print("Maintenance tasks completed.")
    except Exception as e:
        print(f"Error executing maintenance tasks: {e}")
        messagebox.showerror("Error", f"Error executing maintenance tasks: {e}")

def christitus():
    try:
        subprocess.run("powershell -Command \"& {iwr -useb https://christitus.com/win | iex}\"", shell=True, check=True)
    except Exception as e:
        print(f"Failed to execute Chris Titus script: {e}")
        messagebox.showerror("Error", f"Failed to execute Chris Titus script: {e}")


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

# ComboBox and Button for MBR2GPT options
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
run_button.grid(row=3, column=0, padx=20, pady=15, sticky="w")

create_label_with_image("Ghosty Tools", "image_1.png", 0, 0)

# Create Button with Image
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
        command=lambda: [play_click_sound(), command()]  # Play sound when clicked
    )
    button.grid(row=row, column=column, padx=20, pady=15, sticky="w")

# Mini-game: Click the Target
def play_mini_game():
    # Start a separate Pygame instance for the mini-game
    pygame.display.set_mode((400, 300))
    pygame.display.set_caption("Click the Target")
    
    # Define target properties
    target_color = (255, 0, 0)  # Red color
    target_radius = 20
    target_pos = (random.randint(target_radius, 380), random.randint(target_radius, 280))

    # Set up game variables
    score = 0
    game_duration = 15  # Game time limit in seconds
    start_time = time.time()

# Mini-game: Click the Target
def play_mini_game():
    # Initialize the Pygame font module
    pygame.font.init()
    
    # Start a separate Pygame instance for the mini-game
    pygame.display.set_mode((400, 300))
    pygame.display.set_caption("Click the Target")
    
    # Define target properties
    target_color = "#993cda"  # Red color
    target_radius = 20
    target_pos = (random.randint(target_radius, 380), random.randint(target_radius, 280))

    # Set up game variables
    score = 0
    game_duration = 15  # Game time limit in seconds
    start_time = time.time()

    # Game loop
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
                # Check if mouse click is within the target
                distance = ((mouse_pos[0] - target_pos[0]) ** 2 + (mouse_pos[1] - target_pos[1]) ** 2) ** 0.5
                if distance <= target_radius:
                    click_sound.play()  # Play the click sound
                    score += 1
                    # Move target to a new random location
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
    messagebox.showinfo("Mini-Game Over", f"Your score: {score}")

# Mini-game: Tic-Tac-Toe
def play_tic_tac_toe():
    pygame.display.set_mode((400, 400))
    pygame.display.set_caption("Tic-Tac-Toe")

    # Color definitions
    WHITE = (255, 255, 255)
    RED = (255, 0, 0)
    BLUE = (0, 0, 255)

    # Initialize game variables
    grid = [['' for _ in range(3)] for _ in range(3)]
    current_player = 'X'
    game_over = False

    def draw_grid():
        # Draw grid lines
        for i in range(1, 3):
            pygame.draw.line(pygame.display.get_surface(), WHITE, (0, i * 133), (400, i * 133), 2)
            pygame.draw.line(pygame.display.get_surface(), WHITE, (i * 133, 0), (i * 133, 400), 2)

    def draw_marks():
        # Draw the marks on the grid
        for row in range(3):
            for col in range(3):
                mark = grid[row][col]
                if mark == 'X':
                    pygame.draw.line(pygame.display.get_surface(), RED, (col * 133 + 20, row * 133 + 20), (col * 133 + 113, row * 133 + 113), 2)
                    pygame.draw.line(pygame.display.get_surface(), RED, (col * 133 + 20, row * 133 + 113), (col * 133 + 113, row * 133 + 20), 2)
                elif mark == 'O':
                    pygame.draw.circle(pygame.display.get_surface(), BLUE, (col * 133 + 67, row * 133 + 67), 50, 2)

    def check_winner():
        # Check rows, columns, and diagonals for a winner
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

    # Game loop
    running = True
    while running:
        pygame.display.get_surface().fill((30, 30, 30))  # Dark background
        draw_grid()
        draw_marks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
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

            # Reset game on 'R' key press
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                grid = [['' for _ in range(3)] for _ in range(3)]
                current_player = 'X'
                game_over = False

        # Update the display
        pygame.display.flip()

    # Clean up
    pygame.display.quit()

select_all_var = ctk.BooleanVar()

# Create a checkbox for "Select All"
select_all_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Select All Tweaks",
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=select_all_var,
    command=lambda: toggle_all_checkboxes(select_all_var.get())
)
select_all_checkbox.grid(row=8, column=2, padx=20, pady=10, sticky="w")

def toggle_all_checkboxes(select_all):
    # Set the state of all checkboxes based on "Select All"
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
    # Add any other checkbox variables here if you have more


# Create a variable for the checkbox to set services to manual
set_services_manual_var = ctk.BooleanVar()

# Create a checkbox for setting services to manual
set_services_manual_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Set Services to Manual",
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=set_services_manual_var
)
set_services_manual_checkbox.grid(row=2, column=3, padx=20, pady=10, sticky="w")

def set_services_to_manual(service_names):
    # Set specified services to manual startup
    for service in service_names:
        try:
            command = f'Sc config "{service}" start= demand'
            subprocess.run(command, shell=True, check=True)
            print(f"Service '{service}' set to manual.")  # Debug output
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"Failed to set service '{service}' to manual: {e}")

# List of services to set to manual (Add or remove services as needed)
services_to_set_manual = [
    "wuauserv",  # Windows Update
    "BITS",      # Background Intelligent Transfer Service
    "Dnscache",  # DNS Client
    # Add more services as needed
]


run_disk_cleanup_var = ctk.BooleanVar()

# Create a checkbox for running Disk Cleanup
run_disk_cleanup_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Run Disk Cleanup",
    fg_color="#4158D0",
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

# Create a variable for the checkbox to enable End Task with Right Click
enable_end_task_var = ctk.BooleanVar()

# Create a checkbox for enabling End Task with Right Click
enable_end_task_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Enable End Task With Right Click",
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=enable_end_task_var
)
enable_end_task_checkbox.grid(row=5, column=2, padx=20, pady=10, sticky="w")

def enable_end_task():
    # Modify the registry to enable End Task with Right Click
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "NoViewContextMenu", 0, winreg.REG_DWORD, 0)  # Set to 0 to enable context menu
        winreg.CloseKey(key)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to enable End Task with Right Click: {e}")


# Create a variable for the checkbox to disable Wi-Fi Sense
disable_wifi_sense_var = ctk.BooleanVar()

# Create a checkbox for disabling Wi-Fi Sense
disable_wifi_sense_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Disable Wi-Fi Sense",
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=disable_wifi_sense_var
)
disable_wifi_sense_checkbox.grid(row=4, column=4, padx=20, pady=10, sticky="w")

def disable_wifi_sense():
    # Modify the registry to disable Wi-Fi Sense
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\WiFi", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "WifiSense", 0, winreg.REG_DWORD, 0)  # Set to 0 to disable Wi-Fi Sense
        winreg.CloseKey(key)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to disable Wi-Fi Sense: {e}")

# Create a variable for the checkbox to disable Storage Sense
disable_storage_sense_var = ctk.BooleanVar()

# Create a checkbox for disabling Storage Sense
disable_storage_sense_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Disable Storage Sense",
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=disable_storage_sense_var
)
disable_storage_sense_checkbox.grid(row=3, column=4, padx=20, pady=10, sticky="w")

def disable_storage_sense():
    # Modify the registry to disable Storage Sense
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\StorageSense\State", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "Image", 0, winreg.REG_DWORD, 0)  # Set to 0 to disable Storage Sense
        winreg.CloseKey(key)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to disable Storage Sense: {e}")

# Create a variable for the checkbox to disable location tracking
disable_location_tracking_var = ctk.BooleanVar()

# Create a checkbox for disabling location tracking
disable_location_tracking_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Disable Location Tracking",
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=disable_location_tracking_var
)
disable_location_tracking_checkbox.grid(row=2, column=4, padx=20, pady=10, sticky="w")

def disable_location_tracking():
    # Modify the registry to disable location tracking
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "Value", 0, winreg.REG_DWORD, 0)  # Set to 0 to disable location tracking
        winreg.CloseKey(key)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to disable location tracking: {e}")

# Create a variable for the checkbox to prefer IPv4 over IPv6
prefer_ipv4_var = ctk.BooleanVar()

# Create a checkbox for preferring IPv4 over IPv6
prefer_ipv4_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Prefer IPv4 over IPv6",
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=prefer_ipv4_var
)
prefer_ipv4_checkbox.grid(row=1, column=4, padx=20, pady=10, sticky="w")

def prefer_ipv4():
    # Modify the registry to prefer IPv4 over IPv6
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\TCPIP\Parameters", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "IPEnableRouter", 0, winreg.REG_DWORD, 1)  # Set to 1 to prefer IPv4
        winreg.CloseKey(key)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to configure IP preference: {e}")

disable_homegroup_var = ctk.BooleanVar()

# Create a checkbox for disabling HomeGroup
disable_homegroup_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Disable HomeGroup",
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=disable_homegroup_var
)
disable_homegroup_checkbox.grid(row=4, column=3, padx=20, pady=10, sticky="w")

def disable_homegroup():
    # Modify the registry to disable HomeGroup
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "HomeGroupDisabled", 1, winreg.REG_DWORD, 1)  # Set to 1 to disable HomeGroup
        winreg.CloseKey(key)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to disable HomeGroup: {e}")



# Create a variable for the checkbox to delete temp files
delete_temp_files_var = ctk.BooleanVar()

# Create a checkbox for deleting temporary files
delete_temp_files_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Delete Temporary Files",
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=delete_temp_files_var
)
delete_temp_files_checkbox.grid(row=2, column=2, padx=20, pady=10, sticky="w")

def delete_temp_files():
    # Get the path to the temporary files directory
    temp_folder = os.path.join(os.getenv('TEMP'))
    
    # Check if the temporary files folder exists
    if not os.path.exists(temp_folder):
        messagebox.showerror("Error", "Temporary files folder not found.")
        return
    
    try:
        # List files in the temp directory
        for filename in os.listdir(temp_folder):
            file_path = os.path.join(temp_folder, filename)
            # Check if it's a file (skip directories)
            if os.path.isfile(file_path):
                os.remove(file_path)  # Delete the file
                print(f"Deleted: {file_path}")  # Debug output
    except Exception as e:
        print(f"Error deleting temporary files: {e}")  # Debug output
        messagebox.showerror("Error", f"Error deleting temporary files: {e}")

disable_hibernation_var = ctk.BooleanVar()

# Create a checkbox for disabling hibernation
disable_hibernation_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Disable Hibernation",
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=disable_hibernation_var
)
disable_hibernation_checkbox.grid(row=3, column=3, padx=20, pady=10, sticky="w")


def disable_hibernation():
    # Disable hibernation using the command line
    try:
        subprocess.run('powercfg -h off', shell=True, check=True)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to disable hibernation: {e}")

# Create a variable for the checkbox to disable telemetry
disable_telemetry_var = ctk.BooleanVar()

# Create a checkbox for disabling telemetry
disable_telemetry_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Disable Telemetry",
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=disable_telemetry_var
)
disable_telemetry_checkbox.grid(row=3, column=2, padx=20, pady=10, sticky="w")

def disable_telemetry():
    # Modify the registry to disable telemetry
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "AllowTelemetry", 0, winreg.REG_DWORD, 0)  # Set to 0 to disable telemetry
        winreg.CloseKey(key)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to disable telemetry: {e}")

# Create a variable for the checkbox to disable activity history
disable_activity_history_var = ctk.BooleanVar()

# Create a checkbox for disabling activity history
disable_activity_history_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Disable Activity History",
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=disable_activity_history_var
)
disable_activity_history_checkbox.grid(row=4, column=2, padx=20, pady=10, sticky="w")

def disable_activity_history():
    # Modify the registry to disable activity history
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Privacy", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "ActivityHistoryEnabled", 0, winreg.REG_DWORD, 0)  # Set to 0 to disable activity history
        winreg.CloseKey(key)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to disable activity history: {e}")

# Create a variable for the checkbox to disable GameDVR
disable_gamedvr_var = ctk.BooleanVar()

# Create a checkbox for disabling GameDVR
disable_gamedvr_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Disable GameDVR",
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=disable_gamedvr_var
)
disable_gamedvr_checkbox.grid(row=1, column=3, padx=20, pady=10, sticky="w")

def disable_gamedvr():
    # Modify the registry to disable GameDVR
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\GameDVR", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "AppCaptureEnabled", 0, winreg.REG_DWORD, 0)  # Set to 0 to disable GameDVR
        winreg.CloseKey(key)

        # Also, disable Game Bar if desired
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\GameDVR", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "GameDVR_Enabled", 0, winreg.REG_DWORD, 0)  # Set to 0 to disable Game Bar
        winreg.CloseKey(key)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to disable GameDVR: {e}")

create_restore_point_var = ctk.BooleanVar()

# Create a checkbox for creating a restore point
create_restore_point_checkbox = ctk.CTkCheckBox(
    master=app,
    text="Create Restore Point",
    fg_color="#4158D0",
    hover_color="#993cda",
    border_color="#e7e7e7",
    border_width=2,
    variable=create_restore_point_var
)
create_restore_point_checkbox.grid(row=1, column=2, padx=20, pady=10, sticky="w")

def create_restore_point():
    if messagebox.askyesno("Create Restore Point", "Proceed to create a restore point?"):
        try:
            command = "Checkpoint-Computer -Description 'Restore Point created by Ghosty Tool' -RestorePointType 'APPLICATION_INSTALL'"
            subprocess.run(f'powershell -Command "{command}"', shell=True, check=True)
        except Exception as e:
            print(f"Error creating restore point: {e}")
            messagebox.showerror("Error", f"Error creating restore point: {e}")

# Confirm button
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



    messagebox.showinfo("Settings Applied", "Your changes have been applied.")




# Initialize Buttons
create_button_with_image("repairlogo.png", "Run System Maintenance", run_system_maintenance, 1, 0)
# Add a button to the app window to play the mini-game
create_button("Play Click The Target", play_mini_game, 4, 1)
create_button("Play Tic-Tac-Toe", play_tic_tac_toe, 5, 1)

# Start app loop
app.mainloop()
