color a

cls

@echo off
echo.              ************************************************************************
echo.              ***       Locate the Drive number you want to use for MBR2GPT        *** 
echo.              ***                                                                  ***
echo.              ***                           GHOSTY-TOOLS                           ***
echo.              ************************************************************************

pause

color 8

diskmgmt.msc

cls

color d

echo.             *************************************************************************
echo.             ***      Edit [NUMBER] to the Drive number you want to use, Exp-      ***
echo.             ***               (mbr2gpt /validate /disk:1 /allowFullOS).           ***
echo.             ***                      Then save as .bat and exit                   ***
echo.             ***                                                                   ***
echo.             ***                                                                   ***
echo.             ***                             GHOSTY-TOOLS                          ***
echo.             *************************************************************************

pause

color 8

notepad.exe MBR2GPT-Conf.txt

pause

start MBR2GPT-Conf.bat


