
REM           SETUP
@echo off
TITLE Ghosty-Tools
color 0f
mode con cols=120 lines=35
chcp 65001 >nul

REM  --> Check for permissions  
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"  

REM --> If error flag set, we do not have admin.  
if '%errorlevel%' NEQ '0' (  
    echo Requesting administrative privileges...  
    goto UACPrompt  
) else ( goto gotAdmin )  

:UACPrompt  
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"  
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
    "%temp%\getadmin.vbs"
    exit /B  

:gotAdmin  
    if exist "%temp%\getadmin.vbs" ( del "%temp%\getadmin.vbs" )   
    pushd "%CD%"  
    CD /D "%~dp0"  

cls

:Menu

color

cls

CALL :LOGO
echo]
echo]
echo [90m^>[97m1	[95mGhosty-Tools
echo [90m^>[97m2	[94mChris-Titus
echo [90m^>[97m3	[92mMBR2GPT
echo [90m^>[97m4	[97mWindows-Update
echo [90m^>[97m5	[91mEXT
echo]
SET selection=
SET /P selection=

IF /I '%selection%'=='1' GOTO Ghosty-Tools
IF /I '%selection%'=='2' GOTO Chris-Titus
IF /I '%selection%'=='3' GOTO MBR2GPT
IF /I '%selection%'=='4' GOTO windowsupdate
IF /I '%selection%'=='5' GOTO

:Ghosty-Tools
echo]
echo]
echo [97mare you sure you want to run Ghosty-Tools...
echo [97mType Y for yes Or N for no

echo]
SET selection=
SET /P selection=

IF /I '%selection%'=='Y' GOTO Run-Ghosty-Tools
IF /I '%selection%'=='y' GOTO Run-Ghosty-Tools
IF /I '%selection%'=='N' GOTO Menu
IF /I '%selection%'=='n' GOTO Menu

pause
:Run-Ghosty-Tools
::--------------------------------------------------------------------
sfc /scannow

DISM.exe /Online /Cleanup-image /Checkhealth

DISM.exe /Online /Cleanup-image /Scanhealth

DISM.exe /Online /Cleanup-image /Restorehealth

gpupdate

chkdsk /f /r

cleanmgr.exe

defrag c: /u

echo]
echo]
echo [97mDo you want Malwarebytes to be installed...
echo [97mType Y for Yes Or N for No
echo]
SET selection=
SET /P selection=

IF /I '%selection%'=='Y' GOTO Install-Malwarebytes
IF /I '%selection%'=='y' GOTO Install-Malwarebytes
IF /I '%selection%'=='N' GOTO Menu
IF /I '%selection%'=='n' GOTO Menu

pause

:Install-Malwarebytes
winget install Malwarebytes

GOTO Menu
::---------------------------------------------------------------------
:Chris-Titus
powershell -Command "& {iwr -useb https://christitus.com/win | iex}"

GOTO Menu
::---------------------------------------------------------------------
:MBR2GPT
cls
echo ███╗   ███╗██████╗ ██████╗ ██████╗  ██████╗ ██████╗ ████████╗
echo ████╗ ████║██╔══██╗██╔══██╗╚════██╗██╔════╝ ██╔══██╗╚══██╔══╝
echo ██╔████╔██║██████╔╝██████╔╝ █████╔╝██║  ███╗██████╔╝   ██║   
echo ██║╚██╔╝██║██╔══██╗██╔══██╗██╔═══╝ ██║   ██║██╔═══╝    ██║   
echo ██║ ╚═╝ ██║██████╔╝██║  ██║███████╗╚██████╔╝██║        ██║   
echo ╚═╝     ╚═╝╚═════╝ ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝        ╚═╝ 

echo]
echo]
echo [90m^>[97m1	[95mValidate
echo [90m^>[97m2	[94mConvert
echo [90m^>[97m3	[92mBack To Main Menu
echo]
SET selection=
SET /P selection=

IF /I '%selection%'=='1' GOTO validate
IF /I '%selection%'=='2' GOTO Convert
IF /I '%selection%'=='3' GOTO Menu

pause

:Validate

echo]
echo]
echo [97mDAre you sure you want to Validate!...
echo [97mType Y for Yes Or N for No
echo]
SET selection=
SET /P selection=

IF /I '%selection%'=='Y' GOTO Validatenow
IF /I '%selection%'=='y' GOTO Validatetnow
IF /I '%selection%'=='N' GOTO MBR2GPT
IF /I '%selection%'=='n' GOTO MBR2GPT

pause

:Validatenow

cls

echo ███╗   ███╗██████╗ ██████╗ ██████╗  ██████╗ ██████╗ ████████╗
echo ████╗ ████║██╔══██╗██╔══██╗╚════██╗██╔════╝ ██╔══██╗╚══██╔══╝
echo ██╔████╔██║██████╔╝██████╔╝ █████╔╝██║  ███╗██████╔╝   ██║   
echo ██║╚██╔╝██║██╔══██╗██╔══██╗██╔═══╝ ██║   ██║██╔═══╝    ██║   
echo ██║ ╚═╝ ██║██████╔╝██║  ██║███████╗╚██████╔╝██║        ██║   
 

echo]
echo]

echo [90m^>[97m0	[97mValidate Disk 0
echo [90m^>[97m1	[97mValidate Disk 1
echo [90m^>[97m2	[97mValidate Disk 2
echo [90m^>[97m3	[97mValidate Disk 3
echo [90m^>[97m4	[97mValidate Disk 4
echo [90m^>[97m5	[97mValidate Disk 5
echo [90m^>[97m6	[98mValidate Disk 6
echo [90m^>[97m7	[99mValidate Disk 7
echo [90m^>[97m8	[85mValidate Disk 8
echo [90m^>[97m9	[86mValidate Disk 9
echo [90m^>[97mB	[86mBACK
echo [90m^>[97mM	[86mMAIN MENU

echo]
SET selection=
SET /P selection=

IF /I '%selection%'=='0' GOTO 0
IF /I '%selection%'=='1' GOTO 1
IF /I '%selection%'=='2' GOTO 2
IF /I '%selection%'=='3' GOTO 3
IF /I '%selection%'=='4' GOTO 4
IF /I '%selection%'=='5' GOTO 5
IF /I '%selection%'=='6' GOTO 6
IF /I '%selection%'=='7' GOTO 7
IF /I '%selection%'=='8' GOTO 8
IF /I '%selection%'=='9' GOTO 9
IF /I '%selection%'=='B' GOTO MBR2GPT
IF /I '%selection%'=='b' GOTO MBR2GPT
IF /I '%selection%'=='M' GOTO Menu
IF /I '%selection%'=='m' GOTO Menu

:0
mbr2gpt /validate /disk:0 /allowfullos
pause
cls
GOTO Validatenow
:1
mbr2gpt /validate /disk:1 /allowfullos
pause
cls
GOTO Validatenow
:2
mbr2gpt /validate /disk:2 /allowfullos
pause
cls
GOTO Validatenow
:3
mbr2gpt /validate /disk:3 /allowfullos
pause
cls
GOTO Validatenow
:4
mbr2gpt /validate /disk:4 /allowfullos
pause
cls
GOTO Validatenow
:5
mbr2gpt /validate /disk:5 /allowfullos
pause
cls
GOTO Validatenow
:6
mbr2gpt /validate /disk:6 /allowfullos
pause
cls
GOTO Validatenow
:7
mbr2gpt /validate /disk:7 /allowfullos
pause
cls
GOTO Validatenow
:8
mbr2gpt /validate /disk:8 /allowfullos
pause
cls
GOTO Validatenow
:9
mbr2gpt /validate /disk:9 /allowfullos
pause
cls
GOTO Validatenow


:Convert

echo]
echo]
echo [97mDAre you sure you want to Convert!...
echo [97mType Y for Yes Or N for No
echo]
SET selection=
SET /P selection=

IF /I '%selection%'=='Y' GOTO Convertnow
IF /I '%selection%'=='y' GOTO Convertnow
IF /I '%selection%'=='N' GOTO MBR2GPT
IF /I '%selection%'=='n' GOTO MBR2GPT

pause


:Convertnow

cls

echo ███╗   ███╗██████╗ ██████╗ ██████╗  ██████╗ ██████╗ ████████╗
echo ████╗ ████║██╔══██╗██╔══██╗╚════██╗██╔════╝ ██╔══██╗╚══██╔══╝
echo ██╔████╔██║██████╔╝██████╔╝ █████╔╝██║  ███╗██████╔╝   ██║   
echo ██║╚██╔╝██║██╔══██╗██╔══██╗██╔═══╝ ██║   ██║██╔═══╝    ██║   
echo ██║ ╚═╝ ██║██████╔╝██║  ██║███████╗╚██████╔╝██║        ██║   
 

echo]
echo]

echo [90m^>[97m0	[97mConvert Disk 0
echo [90m^>[97m1	[97mConvert Disk 1
echo [90m^>[97m2	[97mConvert Disk 2
echo [90m^>[97m3	[97mConvert Disk 3
echo [90m^>[97m4	[97mConvert Disk 4
echo [90m^>[97m5	[97mConvert Disk 5
echo [90m^>[97m6	[98mConvert Disk 6
echo [90m^>[97m7	[99mConvert Disk 7
echo [90m^>[97m8	[85mConvert Disk 8
echo [90m^>[97m9	[86mConvert Disk 9
echo [90m^>[97mB	[86mBACK
echo [90m^>[97mM	[86mMAIN MENU

echo]
SET selection=
SET /P selection=

IF /I '%selection%'=='0' GOTO 0
IF /I '%selection%'=='1' GOTO 1
IF /I '%selection%'=='2' GOTO 2
IF /I '%selection%'=='3' GOTO 3
IF /I '%selection%'=='4' GOTO 4
IF /I '%selection%'=='5' GOTO 5
IF /I '%selection%'=='6' GOTO 6
IF /I '%selection%'=='7' GOTO 7
IF /I '%selection%'=='8' GOTO 8
IF /I '%selection%'=='9' GOTO 9
IF /I '%selection%'=='B' GOTO MBR2GPT
IF /I '%selection%'=='b' GOTO MBR2GPT
IF /I '%selection%'=='M' GOTO Menu
IF /I '%selection%'=='m' GOTO Menu

:0
mbr2gpt /convert /disk:0 /allowfullos
pause
cls
GOTO Convertnow
:1
mbr2gpt /convert /disk:1 /allowfullos
pause
cls
GOTO Convertnow
:2
mbr2gpt /convert /disk:2 /allowfullos
pause
cls
GOTO Convertnow
:3
mbr2gpt /convert /disk:3 /allowfullos
pause
cls
GOTO Convertnow
:4
mbr2gpt /convert /disk:4 /allowfullos
pause
cls
GOTO Convertnow
:5
mbr2gpt /convert /disk:5 /allowfullos
pause
cls
GOTO Convertnow
:6
mbr2gpt /convert /disk:6 /allowfullos
pause
cls
GOTO Convertnow
:7
mbr2gpt /convert /disk:7 /allowfullos
pause
cls
GOTO Convertnow
:8
mbr2gpt /convert /disk:8 /allowfullos
pause
cls
GOTO Convertnow
:9
mbr2gpt /convert /disk:9 /allowfullos
pause
cls
GOTO Convertnow

:windowsupdate

powershell -Command "& {Install-Module PSWindowsUpdate}"

cls

echo ██╗    ██╗██╗███╗   ██╗██████╗  ██████╗ ██╗    ██╗███████╗      ██╗   ██╗██████╗ ██████╗  █████╗ ████████╗███████╗
echo ██║    ██║██║████╗  ██║██╔══██╗██╔═══██╗██║    ██║██╔════╝      ██║   ██║██╔══██╗██╔══██╗██╔══██╗╚══██╔══╝██╔════╝
echo ██║ █╗ ██║██║██╔██╗ ██║██║  ██║██║   ██║██║ █╗ ██║███████╗█████╗██║   ██║██████╔╝██║  ██║███████║   ██║   █████╗  
echo ██║███╗██║██║██║╚██╗██║██║  ██║██║   ██║██║███╗██║╚════██║╚════╝██║   ██║██╔═══╝ ██║  ██║██╔══██║   ██║   ██╔══╝  
echo ╚███╔███╔╝██║██║ ╚████║██████╔╝╚██████╔╝╚███╔███╔╝███████║      ╚██████╔╝██║     ██████╔╝██║  ██║   ██║   ███████╗


echo]
echo]

echo [90m^>[97m1	[97mDownload but not install the updates.                        
echo [90m^>[97m2	[97mInstall the updates.    
echo [90m^>[97m3	[97mMAIN MENU                                                    
echo]
SET selection=
SET /P selection=

IF /I '%selection%'=='1' GOTO Download
IF /I '%selection%'=='2' GOTO Install
IF /I '%selection%'=='3' GOTO Menu


:Download
powershell -Command "& {Get-WindowsUpdate}"
cls
GOTO windowsupdate

:Install
powershell -Command "& {Install-WindowsUpdate}"
cls

echo ██╗   ██╗██████╗ ██████╗  █████╗ ████████╗███████╗███████╗    ███████╗██╗███╗   ██╗██╗███████╗██╗  ██╗███████╗██████╗ 
echo ██║   ██║██╔══██╗██╔══██╗██╔══██╗╚══██╔══╝██╔════╝██╔════╝    ██╔════╝██║████╗  ██║██║██╔════╝██║  ██║██╔════╝██╔══██╗
echo ██║   ██║██████╔╝██║  ██║███████║   ██║   █████╗  ███████╗    █████╗  ██║██╔██╗ ██║██║███████╗███████║█████╗  ██║  ██║
echo ██║   ██║██╔═══╝ ██║  ██║██╔══██║   ██║   ██╔══╝  ╚════██║    ██╔══╝  ██║██║╚██╗██║██║╚════██║██╔══██║██╔══╝  ██║  ██║
echo ╚██████╔╝██║     ██████╔╝██║  ██║   ██║   ███████╗███████║    ██║     ██║██║ ╚████║██║███████║██║  ██║███████╗██████╔╝
echo  ╚═════╝ ╚═╝     ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚══════╝    ╚═╝     ╚═╝╚═╝  ╚═══╝╚═╝╚══════╝╚═╝  ╚═╝╚══════╝╚═════╝

pause


::----------------------------------------------------------------------

cls

GOTO Menu
pause >nul






  



REM       LOGO

:LOGO

echo       ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗██╗   ██╗           ████████╗ ██████╗  ██████╗ ██╗     ███████╗
echo      ██╔════╝ ██║  ██║██╔═══██╗██╔════╝╚══██╔══╝╚██╗ ██╔╝           ╚══██╔══╝██╔═══██╗██╔═══██╗██║     ██╔════╝
echo      ██║  ███╗███████║██║   ██║███████╗   ██║    ╚████╔╝               ██║   ██║   ██║██║   ██║██║     ███████╗
echo      ██║   ██║██╔══██║██║   ██║╚════██║   ██║     ╚██╔╝                ██║   ██║   ██║██║   ██║██║     ╚════██║
echo      ╚██████╔╝██║  ██║╚██████╔╝███████║   ██║      ██║       ██╗       ██║   ╚██████╔╝╚██████╔╝███████╗███████║
echo       ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝      ╚═╝       ╚═╝       ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝╚══════╝


