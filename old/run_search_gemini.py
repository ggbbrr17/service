import os
import time
import pyautogui

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

os.system("start chrome")
time.sleep(2.5)
pyautogui.hotkey('ctrl', 'l')
time.sleep(0.2)
pyautogui.write('gemini')
print('Typed gemini')
